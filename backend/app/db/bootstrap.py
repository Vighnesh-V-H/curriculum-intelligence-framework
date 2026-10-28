import logging

from app.core.config import get_settings
from app.core.security import get_password_service
from app.db.models.user import RoleCode, User, UserRole, UserStatus
from app.db.session import SessionLocal
from app.repositories.roles import RoleRepository
from app.repositories.users import UserRepository

logger = logging.getLogger(__name__)


def bootstrap_admin() -> None:
    settings = get_settings()
    password = (
        settings.bootstrap_admin_password.get_secret_value()
        if settings.bootstrap_admin_password is not None
        else ""
    )
    if not password:
        return

    with SessionLocal() as session:
        users = UserRepository(session)
        username = settings.bootstrap_admin_username.strip().lower()
        if users.exists_username(username):
            return

        roles = RoleRepository(session)
        admin_role = roles.get_by_code(RoleCode.ADMIN.value)
        if admin_role is None:
            logger.warning(
                "ADMIN role is missing; apply database migrations before starting the API"
            )
            return

        user = User(
            username=username,
            email=settings.bootstrap_admin_email.strip().lower(),
            password_hash=get_password_service().hash(password),
            full_name="System Administrator",
            status=UserStatus.ACTIVE.value,
        )
        users.add(user)
        users.add_role_assignment(UserRole(user_id=user.id, role_id=admin_role.id))
        session.commit()
        logger.info("Bootstrap administrator '%s' created", username)
