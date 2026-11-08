import uuid

from sqlalchemy import select

from app.db.models import GraphProjectionJob, GraphProjectionJobStatus
from app.db.session import SessionLocal
from app.services.knowledge_graph_worker import KnowledgeGraphWorker
from tests.conftest import bearer


class SuccessfulProjection:
    def __init__(self):
        self.calls = []

    def rebuild(self, curriculum_id, version_id, **_kwargs):
        self.calls.append((curriculum_id, version_id))


class FailedProjection:
    def rebuild(self, _curriculum_id, _version_id, **_kwargs):
        raise ConnectionError("sensitive connection details should not be stored")


def create_curriculum(client, faculty_token, program):
    response = client.post(
        "/api/v1/curricula",
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": "2026",
            "duration_years": 4,
            "semesters": [{"semester_number": 1, "name": "Semester 1"}],
            "courses": [],
        },
        headers=bearer(faculty_token),
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["versions"][0]["id"])


def test_worker_completes_queued_projection_jobs(client, faculty_token, program):
    version_id = create_curriculum(client, faculty_token, program)
    service = SuccessfulProjection()
    with SessionLocal() as session:
        processed = KnowledgeGraphWorker(session, service).process()

    assert processed > 0
    assert service.calls
    with SessionLocal() as session:
        jobs = session.scalars(
            select(GraphProjectionJob).where(GraphProjectionJob.curriculum_version_id == version_id)
        ).all()
    assert all(job.status == GraphProjectionJobStatus.COMPLETED.value for job in jobs)


def test_worker_retries_then_marks_exhausted_job_failed(client, faculty_token, program):
    version_id = create_curriculum(client, faculty_token, program)
    with SessionLocal() as session:
        processed = KnowledgeGraphWorker(session, FailedProjection(), max_attempts=1).process()

    assert processed > 0
    with SessionLocal() as session:
        jobs = session.scalars(
            select(GraphProjectionJob).where(GraphProjectionJob.curriculum_version_id == version_id)
        ).all()
    assert all(job.status == GraphProjectionJobStatus.FAILED.value for job in jobs)
    assert all(job.last_error == "ConnectionError" for job in jobs)
