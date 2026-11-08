import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CurriculumVersion, GraphProjectionJob, GraphProjectionJobStatus
from app.db.models.user import utc_now
from app.services.knowledge_graph_projection import KnowledgeGraphProjectionService

logger = logging.getLogger(__name__)


class KnowledgeGraphWorker:
    def __init__(
        self,
        session: Session,
        service: KnowledgeGraphProjectionService,
        worker_id: str | None = None,
        max_attempts: int = 5,
    ) -> None:
        self._session = session
        self._service = service
        self._worker_id = worker_id or str(uuid.uuid4())
        self._max_attempts = max_attempts

    def process(self, limit: int = 20) -> int:
        stale_before = utc_now() - timedelta(minutes=5)
        jobs = self._session.scalars(
            select(GraphProjectionJob)
            .where(
                (GraphProjectionJob.status == GraphProjectionJobStatus.PENDING.value)
                | (
                    (GraphProjectionJob.status == GraphProjectionJobStatus.PROCESSING.value)
                    & (GraphProjectionJob.claimed_at < stale_before)
                )
            )
            .order_by(GraphProjectionJob.requested_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        if not jobs:
            return 0

        for job in jobs:
            job.status = GraphProjectionJobStatus.PROCESSING.value
            job.worker_id = self._worker_id
            job.claimed_at = utc_now()
            job.attempts += 1
        self._session.commit()

        processed = 0
        for job in jobs:
            try:
                version = self._session.get(CurriculumVersion, job.curriculum_version_id)
                if version is None:
                    job.status = GraphProjectionJobStatus.COMPLETED.value
                else:
                    self._service.rebuild(
                        version.curriculum_id, version.id, record_completion=False
                    )
                    job.status = GraphProjectionJobStatus.COMPLETED.value
                job.completed_at = utc_now()
                job.last_error = None
            except Exception as exc:
                job.last_error = type(exc).__name__
                job.status = (
                    GraphProjectionJobStatus.FAILED.value
                    if job.attempts >= self._max_attempts
                    else GraphProjectionJobStatus.PENDING.value
                )
                logger.warning(
                    "Curriculum graph projection failed",
                    extra={
                        "curriculum_version_id": str(job.curriculum_version_id),
                        "job_id": str(job.id),
                        "attempts": job.attempts,
                        "error_type": type(exc).__name__,
                    },
                )
            self._session.commit()
            processed += 1
        return processed
