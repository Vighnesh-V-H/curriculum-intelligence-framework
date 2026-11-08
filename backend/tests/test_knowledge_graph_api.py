from tests.conftest import bearer


def test_graph_query_requires_authentication(client):
    response = client.get(
        "/api/v1/curricula/00000000-0000-0000-0000-000000000001/versions/"
        "00000000-0000-0000-0000-000000000002/graph"
    )
    assert response.status_code == 401


def test_graph_api_returns_service_unavailable_when_not_configured(client, faculty_token):
    response = client.get(
        "/api/v1/curricula/00000000-0000-0000-0000-000000000001/versions/"
        "00000000-0000-0000-0000-000000000002/graph",
        headers=bearer(faculty_token),
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "graph_unavailable"


def test_reviewer_cannot_request_graph_rebuild(client, reviewer_token):
    response = client.post(
        "/api/v1/curricula/00000000-0000-0000-0000-000000000001/versions/"
        "00000000-0000-0000-0000-000000000002/graph/rebuild",
        headers=bearer(reviewer_token),
    )
    assert response.status_code == 403
