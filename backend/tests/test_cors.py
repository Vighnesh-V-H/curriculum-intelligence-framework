


def test_options_preflight_allows_localhost_variants(client):
    for origin in (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.1.110:3000",
    ):
        response = client.options(
            "/api/v1/documents",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200, origin
        assert response.headers["access-control-allow-origin"] == origin, origin


def test_options_preflight_rejects_unknown_origin(client):
    response = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "https://curriculum.example.attacker",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers
