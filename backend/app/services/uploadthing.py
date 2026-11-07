import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from sqids import Sqids

from app.core.errors import ServiceUnavailableError
from app.core.logging_config import safe_exception_details

UPLOADTHING_VERSION = "7.7.4"
_KEY_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_PRESIGN_TTL_SECONDS = 3600
_READ_TTL_SECONDS = 300
_SIGNATURE_PREFIX = "hmac-sha256="
logger = logging.getLogger(__name__)


class UploadThingError(Exception):
    """Raised when the UploadThing transport fails or answers unusably."""


class UploadThingNotConfiguredError(ServiceUnavailableError):
    def __init__(
        self, message: str = "File storage is not configured; set UPLOADTHING_TOKEN"
    ) -> None:
        super().__init__(message, "storage_not_configured")


@dataclass(frozen=True)
class UploadedFile:
    key: str
    ufs_url: str
    file_hash: str | None


@dataclass(frozen=True)
class UploadThingCredentials:
    api_key: str
    app_id: str
    ingest_url: str
    ufs_url_base: str
    ufs_app_id_location: str


class UploadThingClient(Protocol):
    def upload_file(
        self, data: bytes, filename: str, content_type: str | None
    ) -> UploadedFile: ...

    def read_file(self, key: str) -> bytes: ...


def _utf16_codes(text: str) -> list[int]:
    encoded = text.encode("utf-16-le")
    return [
        encoded[index] | (encoded[index + 1] << 8)
        for index in range(0, len(encoded), 2)
    ]


def effect_hash_string(text: str) -> int:
    shadow = 5381
    for code in reversed(_utf16_codes(text)):
        shadow = ((shadow * 33) & 0xFFFFFFFF) ^ code
    value = (shadow & 0xBFFFFFFF) | ((shadow >> 1) & 0x40000000)
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def _truncated_remainder(dividend: int, divisor: int) -> int:
    remainder = abs(dividend) % divisor
    return -remainder if dividend < 0 else remainder


def _shuffle_alphabet(alphabet: str, seed: str) -> str:
    seed_number = effect_hash_string(seed)
    chars = list(alphabet)
    length = len(chars)
    for index in range(length):
        target = (_truncated_remainder(seed_number, index + 1) + index) % length
        chars[index], chars[target] = chars[target], chars[index]
    return "".join(chars)


def _generate_file_key(
    app_id: str, filename: str, size: int, content_type: str, now_ms: int
) -> str:
    seed = json.dumps([filename, size, content_type, now_ms, now_ms])
    alphabet = _shuffle_alphabet(_KEY_ALPHABET, app_id)
    app_part = Sqids(alphabet=alphabet, min_length=12).encode(
        [abs(effect_hash_string(app_id))]
    )
    file_part = Sqids(alphabet=alphabet, min_length=36).encode(
        [abs(effect_hash_string(seed))]
    )
    return app_part + file_part


def _js_query_encode(value: str) -> str:
    output = []
    for byte in str(value).encode("utf-8"):
        char = chr(byte)
        is_alnum = (0x41 <= byte <= 0x5A) or (0x61 <= byte <= 0x7A) or (0x30 <= byte <= 0x39)
        if is_alnum or char in "*-._":
            output.append(char)
        elif byte == 0x20:
            output.append("+")
        else:
            output.append(f"%{byte:02X}")
    return "".join(output)


def _sign_url(url: str, api_key: str) -> str:
    digest = hmac.new(
        api_key.encode("utf-8"), url.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{_SIGNATURE_PREFIX}{digest}"


def _utc_now_ms() -> int:
    return int(time.time() * 1000)


class HttpxUploadThingClient:
    def __init__(
        self,
        credentials: UploadThingCredentials,
        timeout_seconds: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._credentials = credentials
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    def upload_file(
        self, data: bytes, filename: str, content_type: str | None
    ) -> UploadedFile:
        size = len(data)
        key = _generate_file_key(
            self._credentials.app_id, filename, size, content_type or "", _utc_now_ms()
        )
        url = self._presigned_upload_url(key, filename, size, content_type)
        response = self._send(
            "PUT",
            url,
            files={"file": (filename, data, content_type or "application/octet-stream")},
            headers={"Range": "bytes=0-", "x-uploadthing-version": UPLOADTHING_VERSION},
        )
        body = self._parse_json(response, "ufsUrl")
        return UploadedFile(key=key, ufs_url=body["ufsUrl"], file_hash=body.get("fileHash"))

    def read_file(self, key: str) -> bytes:
        response = self._send("GET", self._signed_file_url(key))
        if response.status_code >= 400:
            raise UploadThingError(
                f"UploadThing returned status {response.status_code} when downloading a stored file"
            )
        return response.content

    def _presigned_upload_url(
        self, key: str, filename: str, size: int, content_type: str | None
    ) -> str:
        expires_ms = _utc_now_ms() + _PRESIGN_TTL_SECONDS * 1000
        params: list[tuple[str, str]] = [
            ("expires", str(expires_ms)),
            ("x-ut-identifier", self._credentials.app_id),
            ("x-ut-file-name", filename),
            ("x-ut-file-size", str(size)),
            ("x-ut-file-type", content_type or ""),
            ("x-ut-content-disposition", "inline"),
        ]
        query = "&".join(
            f"{_js_query_encode(name)}={_js_query_encode(value)}" for name, value in params
        )
        source = f"{self._credentials.ingest_url.rstrip('/')}/{key}?{query}"
        signed = _sign_url(source, self._credentials.api_key)
        return f"{source}&signature={_js_query_encode(signed)}"

    def _signed_file_url(self, key: str) -> str:
        credentials = self._credentials
        expires_ms = _utc_now_ms() + _READ_TTL_SECONDS * 1000
        if credentials.ufs_app_id_location == "path":
            base = f"{credentials.ufs_url_base}/a/{credentials.app_id}/{key}"
        else:
            base = f"{credentials.ufs_url_base}/f/{key}"
        source = f"{base}?expires={expires_ms}"
        return f"{source}&signature={_js_query_encode(_sign_url(source, credentials.api_key))}"

    def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        started_at = time.perf_counter()
        logger.info(
            "Storage provider request started",
            extra={"operation": "uploadthing_http", "method": method},
        )
        try:
            if self._http_client is not None:
                response = self._http_client.request(method, url, **kwargs)
            else:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            logger.error(
                "Storage provider transport failed",
                extra={"operation": "uploadthing_http", "method": method,
                       **safe_exception_details(exc)},
            )
            raise UploadThingError(f"UploadThing request failed: {exc}") from exc
        log_method = logger.warning if response.status_code >= 400 else logger.info
        log_method(
            "Storage provider request completed",
            extra={
                "operation": "uploadthing_http",
                "method": method,
                "provider_status": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        return response

    def _parse_json(self, response: httpx.Response, required_key: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise UploadThingError(
                f"UploadThing ingest returned status {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise UploadThingError("UploadThing ingest response is not JSON") from exc
        if not isinstance(body, dict) or required_key not in body:
            raise UploadThingError(
                f"UploadThing ingest response is missing {required_key}"
            )
        return body


def _credentials_from_token(
    token: str, ingest_host: str, ufs_host: str, ufs_app_id_location: str
) -> UploadThingCredentials:
    try:
        payload = json.loads(
            base64.b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
        )
        api_key = str(payload["apiKey"])
        app_id = str(payload["appId"])
        regions = list(payload["regions"])
        region = regions[0]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise UploadThingNotConfiguredError(
            "UPLOADTHING_TOKEN is invalid; expected a base64 JSON token "
            "with apiKey, appId and regions"
        ) from exc
    token_ingest_host = payload.get("ingestHost", ingest_host)
    if ufs_app_id_location == "path":
        ufs_url_base = f"https://{ufs_host}"
    else:
        ufs_url_base = f"https://{app_id}.{ufs_host}"
    return UploadThingCredentials(
        api_key=api_key,
        app_id=app_id,
        ingest_url=f"https://{region}.{token_ingest_host}",
        ufs_url_base=ufs_url_base,
        ufs_app_id_location=ufs_app_id_location,
    )


def build_uploadthing_client() -> UploadThingClient | None:
    from app.core.config import get_settings

    settings = get_settings()
    token = settings.uploadthing_token
    if token is not None and token.get_secret_value() != "":
        return HttpxUploadThingClient(
            _credentials_from_token(
                token.get_secret_value(),
                settings.uploadthing_ingest_host,
                settings.uploadthing_ufs_host,
                settings.uploadthing_ufs_app_id_location,
            ),
            timeout_seconds=settings.uploadthing_timeout_seconds,
        )
    api_key = settings.uploadthing_api_key
    app_id = settings.uploadthing_app_id
    if api_key is None or api_key.get_secret_value() == "" or not app_id:
        return None
    region = settings.uploadthing_region
    if not region:
        raise UploadThingNotConfiguredError(
            "UPLOADTHING_REGION is required when UPLOADTHING_TOKEN is not set"
        )
    if settings.uploadthing_ufs_app_id_location == "path":
        ufs_url_base = f"https://{settings.uploadthing_ufs_host}"
    else:
        ufs_url_base = f"https://{app_id}.{settings.uploadthing_ufs_host}"
    return HttpxUploadThingClient(
        UploadThingCredentials(
            api_key=api_key.get_secret_value(),
            app_id=app_id,
            ingest_url=f"https://{region}.{settings.uploadthing_ingest_host}",
            ufs_url_base=ufs_url_base,
            ufs_app_id_location=settings.uploadthing_ufs_app_id_location,
        ),
        timeout_seconds=settings.uploadthing_timeout_seconds,
    )
