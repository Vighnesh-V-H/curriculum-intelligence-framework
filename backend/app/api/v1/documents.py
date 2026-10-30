import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import (
    get_current_user,
    get_document_service,
    require_roles,
)
from app.db.models.user import RoleCode, User
from app.schemas.document import DocumentResponse
from app.services.documents import DocumentProcessingService

DOCUMENT_WRITE_ROLES = (
    RoleCode.ADMIN,
    RoleCode.COMMITTEE_MEMBER,
    RoleCode.FACULTY,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    actor: User = Depends(require_roles(*DOCUMENT_WRITE_ROLES)),
    uploaded_file: UploadFile = File(..., alias="file"),
    service: DocumentProcessingService = Depends(get_document_service),
) -> DocumentResponse:
    return service.upload(actor, uploaded_file)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> list[DocumentResponse]:
    return service.list_documents()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> DocumentResponse:
    return service.get(document_id)


@router.post("/{document_id}/ingest", response_model=DocumentResponse)
def ingest_document(
    document_id: uuid.UUID,
    actor: User = Depends(require_roles(*DOCUMENT_WRITE_ROLES)),
    service: DocumentProcessingService = Depends(get_document_service),
) -> DocumentResponse:
    return service.ingest(actor, document_id)
