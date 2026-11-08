import uuid

from sqlalchemy import select

from app.db.models import GraphProjectionJob, GraphProjectionJobStatus
from app.db.session import SessionLocal
from app.services.knowledge_graph_projection import KnowledgeGraphProjectionService
from tests.conftest import bearer


class CapturingGraph:
    def __init__(self):
        self.version_id = None
        self.snapshot = None

    def replace_version(self, version_id, snapshot):
        self.version_id = version_id
        self.snapshot = snapshot

    def get_version_graph(self, version_id, limit=1000):
        return {"curriculum_version_id": str(version_id), "nodes": [], "relationships": []}


def test_rebuild_projects_one_curriculum_version(client, faculty_token, program):
    created = client.post(
        "/api/v1/curricula",
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": "2026",
            "duration_years": 4,
            "semesters": [{"semester_number": 1, "name": "Semester 1"}],
            "courses": [
                {
                    "course_code": "CS101",
                    "course_name": "Programming Fundamentals",
                    "course_type_code": "CORE",
                    "credits": 4,
                    "semester_number": 1,
                }
            ],
        },
        headers=bearer(faculty_token),
    )
    assert created.status_code == 201
    curriculum = created.json()
    version = curriculum["versions"][0]

    graph = CapturingGraph()
    with SessionLocal() as session:
        result = KnowledgeGraphProjectionService(session, graph).rebuild(
            uuid.UUID(curriculum["id"]), uuid.UUID(version["id"])
        )

    assert result["node_count"] == 5
    assert graph.version_id == uuid.UUID(version["id"])
    labels = {node["label"] for node in graph.snapshot["nodes"]}
    assert {"Program", "Curriculum", "CurriculumVersion", "Semester", "Course"} == labels
    assert all(
        node.get("curriculum_version_id") in (None, version["id"])
        for node in graph.snapshot["nodes"]
    )


def test_curriculum_write_enqueues_projection_job(client, faculty_token, program):
    created = client.post(
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
    version_id = uuid.UUID(created.json()["versions"][0]["id"])

    with SessionLocal() as session:
        jobs = session.scalars(
            select(GraphProjectionJob).where(GraphProjectionJob.curriculum_version_id == version_id)
        ).all()

    assert created.status_code == 201
    assert jobs
    assert all(job.status == GraphProjectionJobStatus.PENDING.value for job in jobs)
