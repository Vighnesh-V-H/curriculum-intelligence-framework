from __future__ import annotations

import uuid
from typing import Any, Protocol

NODE_LABELS = {
    "Program",
    "Curriculum",
    "CurriculumVersion",
    "Semester",
    "Course",
    "CourseOutcome",
    "ProgramOutcome",
    "PEO",
}
RELATIONSHIP_TYPES = {
    "HAS_VERSION",
    "FOR_PROGRAM",
    "HAS_SEMESTER",
    "HAS_COURSE",
    "SCHEDULED_IN",
    "HAS_OUTCOME",
    "PREREQUISITE_OF",
    "CONTRIBUTES_TO",
    "USES_PO",
    "USES_PEO",
}


class GraphTransaction(Protocol):
    def run(self, query: str, **parameters: Any) -> Any: ...


class GraphSession(Protocol):
    def execute_write(self, work: Any, *args: Any, **kwargs: Any) -> Any: ...
    def execute_read(self, work: Any, *args: Any, **kwargs: Any) -> Any: ...
    def close(self) -> None: ...


class GraphDriver(Protocol):
    def session(self, **kwargs: Any) -> GraphSession: ...
    def verify_connectivity(self) -> None: ...
    def close(self) -> None: ...


class KnowledgeGraphRepository:
    """Idempotent writer and bounded reader for version-scoped graph snapshots."""

    def __init__(self, driver: GraphDriver, database: str | None = None) -> None:
        self._driver = driver
        self._database = database

    def replace_version(self, version_id: uuid.UUID, snapshot: dict[str, Any]) -> None:
        version_key = str(version_id)
        self._validate_snapshot(version_key, snapshot)
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._replace_tx, version_key, snapshot)

    def get_version_graph(self, version_id: uuid.UUID, limit: int = 1000) -> dict[str, Any]:
        version_key = str(version_id)
        with self._driver.session(database=self._database) as session:
            return session.execute_read(self._read_tx, version_key, limit)

    @staticmethod
    def _validate_snapshot(version_id: str, snapshot: dict[str, Any]) -> None:
        if not isinstance(snapshot, dict):
            raise ValueError("Graph snapshot must be an object")
        for node in snapshot.get("nodes", []):
            if node.get("label") not in NODE_LABELS:
                raise ValueError("Unsupported graph node label")
            if not node.get("id"):
                raise ValueError("Graph nodes require a source id")
            if (
                node["label"] not in {"Program", "Curriculum"}
                and node.get("curriculum_version_id") != version_id
            ):
                raise ValueError("Version-scoped node belongs to another curriculum version")
        for edge in snapshot.get("relationships", []):
            if edge.get("type") not in RELATIONSHIP_TYPES:
                raise ValueError("Unsupported graph relationship type")
            if (
                not edge.get("source_id")
                or not edge.get("target_id")
                or edge.get("source_label") not in NODE_LABELS
                or edge.get("target_label") not in NODE_LABELS
            ):
                raise ValueError("Graph relationships require typed source and target ids")

    @staticmethod
    def _replace_tx(tx: GraphTransaction, version_id: str, snapshot: dict[str, Any]) -> None:
        # Delete only version-scoped entities. Shared identity nodes are merged below.
        tx.run(
            "MATCH (n {curriculum_version_id: $version_id}) DETACH DELETE n",
            version_id=version_id,
        )
        for node in snapshot.get("nodes", []):
            label = node["label"]
            props = dict(node)
            props.pop("label", None)
            tx.run(
                f"MERGE (n:{label} {{id: $id}}) SET n += $properties",
                id=props["id"],
                properties=props,
            )
        for edge in snapshot.get("relationships", []):
            rel_type = edge["type"]
            properties = edge.get("properties", {})
            source_label = edge["source_label"]
            target_label = edge["target_label"]
            tx.run(
                f"MATCH (a:{source_label} {{id: $source_id}}), "
                f"(b:{target_label} {{id: $target_id}}) "
                f"MERGE (a)-[r:{rel_type} {{id: $relationship_id}}]->(b) "
                "SET r += $properties",
                source_id=edge["source_id"],
                target_id=edge["target_id"],
                relationship_id=edge["id"],
                properties=properties,
            )

    @staticmethod
    def _read_tx(tx: GraphTransaction, version_id: str, limit: int) -> dict[str, Any]:
        result = tx.run(
            "MATCH (n {curriculum_version_id: $version_id}) "
            "WITH n ORDER BY n.id LIMIT $limit "
            "WITH collect({labels: labels(n), properties: properties(n)}) AS nodes "
            "CALL { MATCH (a {curriculum_version_id: $version_id})-[r]-"
            "(b {curriculum_version_id: $version_id}) "
            "WITH DISTINCT r ORDER BY r.id LIMIT $limit "
            "RETURN collect({type: type(r), properties: properties(r), "
            "source_id: startNode(r).id, target_id: endNode(r).id}) AS relationships } "
            "RETURN nodes, relationships",
            version_id=version_id,
            limit=limit,
        ).single()
        if result is None:
            return {"curriculum_version_id": version_id, "nodes": [], "relationships": []}
        nodes = [node for node in (result["nodes"] or []) if node]
        relationships = [edge for edge in (result["relationships"] or []) if edge.get("type")]
        return {"curriculum_version_id": version_id, "nodes": nodes, "relationships": relationships}

    def close(self) -> None:
        self._driver.close()
