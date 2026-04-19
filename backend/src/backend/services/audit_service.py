import uuid
from typing import Any

from src.backend.db.models import AuditLog
from src.backend.db.session import async_session_factory


async def write_audit_log(
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> None:
    async with async_session_factory() as session:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            reason=reason,
            ip_address=ip_address,
        )
        session.add(entry)
        await session.commit()
