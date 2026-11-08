import uuid

import pytest

from app.services.knowledge_graph import KnowledgeGraphRepository


class FakeResult:
    def single(self):
        return {"nodes": [], "relationships": []}


class FakeSession:
    def __init__(self):
        self.queries: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute_write(self, work, *args):
        return work(self, *args)

    def execute_read(self, work, *args):
        return work(self, *args)

    def run(self, query, **parameters):
        self.queries.append((query, parameters))
        return FakeResult()


class FakeDriver:
    def __init__(self):
        self.sessions: list[FakeSession] = []

    def session(self, **_kwargs):
        session = FakeSession()
        self.sessions.append(session)
        return session

    def close(self):
        pass


def test_replace_version_is_scoped_and_writes_snapshot():
    driver = FakeDriver()
    repository = KnowledgeGraphRepository(driver)
    version_id = uuid.uuid4()
    repository.replace_version(
        version_id,
        {
            "nodes": [
                {"label": "Course", "id": "course-1", "curriculum_version_id": str(version_id)}
            ],
            "relationships": [
                {
                    "type": "HAS_COURSE",
                    "id": "edge-1",
                    "source_label": "CurriculumVersion",
                    "source_id": "version-1",
                    "target_label": "Course",
                    "target_id": "course-1",
                }
            ],
        },
    )

    queries = driver.sessions[0].queries
    assert "DETACH DELETE" in queries[0][0]
    assert queries[0][1]["version_id"] == str(version_id)
    assert len(queries) == 3


def test_replace_version_rejects_cross_version_nodes():
    repository = KnowledgeGraphRepository(FakeDriver())
    with pytest.raises(ValueError, match="another curriculum version"):
        repository.replace_version(
            uuid.uuid4(),
            {
                "nodes": [{"label": "Course", "id": "course-1", "curriculum_version_id": "other"}],
                "relationships": [],
            },
        )


def test_replace_version_rejects_untrusted_labels():
    repository = KnowledgeGraphRepository(FakeDriver())
    with pytest.raises(ValueError, match="Unsupported graph node label"):
        repository.replace_version(
            uuid.uuid4(),
            {"nodes": [{"label": "Injected`, n", "id": "x"}], "relationships": []},
        )


def test_graph_read_returns_version_scoped_empty_result():
    repository = KnowledgeGraphRepository(FakeDriver())
    result = repository.get_version_graph(uuid.uuid4())
    assert result["nodes"] == []
    assert result["relationships"] == []
