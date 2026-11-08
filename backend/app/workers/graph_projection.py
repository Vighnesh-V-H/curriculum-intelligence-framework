import argparse
import logging
import time

from neo4j import GraphDatabase

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.knowledge_graph import KnowledgeGraphRepository
from app.services.knowledge_graph_projection import KnowledgeGraphProjectionService
from app.services.knowledge_graph_worker import KnowledgeGraphWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="Project pending curriculum graph updates")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.neo4j_uri:
        parser.error("NEO4J_URI must be configured to run the graph projection worker")
    auth = None
    if settings.neo4j_password:
        auth = (settings.neo4j_username, settings.neo4j_password.get_secret_value())
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=auth)
    graph = KnowledgeGraphRepository(driver, settings.neo4j_database)
    try:
        while True:
            with SessionLocal() as session:
                service = KnowledgeGraphProjectionService(session, graph)
                processed = KnowledgeGraphWorker(session, service).process(args.batch_size)
            if args.once:
                break
            if processed == 0:
                time.sleep(args.poll_seconds)
    finally:
        graph.close()


if __name__ == "__main__":
    main()
