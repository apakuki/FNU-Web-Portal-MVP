import asyncio
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from src.backend.auth import hash_password
from src.backend.db.models import (
    ChatbotKnowledge,
    KpiDefinition,
    NotificationTemplate,
    User,
)
from src.backend.db.session import async_session_factory

FAQ_SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "chatbot_faq.json"
TEMPLATES_SEED_PATH = (
    Path(__file__).resolve().parents[2] / "seed" / "notification_templates.json"
)
KPI_SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "kpi_definitions.json"

SEED_USERS = [
    {
        "email": "admin@fnu.ac.fj",
        "full_name": "System Administrator",
        "role": "admin",
        "password": "admin123",
        "banner_id": None,
    },
    {
        "email": "staff@fnu.ac.fj",
        "full_name": "Registry Staff",
        "role": "staff",
        "password": "staff123",
        "banner_id": None,
    },
    {
        "email": "finance@fnu.ac.fj",
        "full_name": "Finance Officer",
        "role": "finance",
        "password": "finance123",
        "banner_id": None,
    },
    {
        "email": "lecturer@fnu.ac.fj",
        "full_name": "Dr. Mere Tuisawau",
        "role": "lecturer",
        "password": "lecturer123",
        "banner_id": "L00010001",
    },
    {
        "email": "manager@fnu.ac.fj",
        "full_name": "Dean of CBHTS",
        "role": "manager",
        "password": "manager123",
        "banner_id": None,
    },
    {
        "email": "vc@fnu.ac.fj",
        "full_name": "Vice Chancellor",
        "role": "vc",
        "password": "vc123456",
        "banner_id": None,
    },
    {
        "email": "student@fnu.ac.fj",
        "full_name": "Apisai Delana",
        "role": "student",
        "password": "student123",
        "banner_id": "S00012345",
    },
    {
        "email": "student2@fnu.ac.fj",
        "full_name": "Litia Nabalarua",
        "role": "student",
        "password": "student123",
        "banner_id": "S00012346",
    },
]


async def seed_users(session) -> None:
    for user_data in SEED_USERS:
        result = await session.execute(
            select(User).where(User.email == user_data["email"])
        )
        if result.scalar_one_or_none():
            print(f"  exists: {user_data['email']}")
            continue

        user = User(
            email=user_data["email"],
            full_name=user_data["full_name"],
            role=user_data["role"],
            password_hash=hash_password(user_data["password"]),
            banner_id=user_data["banner_id"],
        )
        session.add(user)
        print(f"  created: {user_data['email']} ({user_data['role']})")


async def seed_chatbot_faq(session) -> None:
    if not FAQ_SEED_PATH.exists():
        print(f"  skipped FAQ seed (missing file: {FAQ_SEED_PATH})")
        return

    entries = json.loads(FAQ_SEED_PATH.read_text())
    for entry in entries:
        existing = await session.scalar(
            select(ChatbotKnowledge).where(ChatbotKnowledge.title == entry["title"])
        )
        if existing:
            print(f"  exists FAQ: {entry['title']}")
            continue
        session.add(
            ChatbotKnowledge(
                kind=entry.get("kind", "faq"),
                title=entry["title"],
                content=entry["content"],
                tags=entry.get("tags", []),
                is_active=True,
            )
        )
        print(f"  created FAQ: {entry['title']}")


async def seed_notification_templates(session) -> None:
    if not TEMPLATES_SEED_PATH.exists():
        print(f"  skipped templates seed (missing file: {TEMPLATES_SEED_PATH})")
        return

    entries = json.loads(TEMPLATES_SEED_PATH.read_text())
    for entry in entries:
        existing = await session.scalar(
            select(NotificationTemplate).where(NotificationTemplate.code == entry["code"])
        )
        if existing:
            print(f"  exists template: {entry['code']}")
            continue
        session.add(
            NotificationTemplate(
                code=entry["code"],
                name=entry["name"],
                channel=entry["channel"],
                subject_template=entry.get("subject_template"),
                body_template=entry["body_template"],
                is_active=True,
            )
        )
        print(f"  created template: {entry['code']}")


async def seed_kpi_definitions(session) -> None:
    if not KPI_SEED_PATH.exists():
        print(f"  skipped KPI seed (missing file: {KPI_SEED_PATH})")
        return

    entries = json.loads(KPI_SEED_PATH.read_text())
    for entry in entries:
        existing = await session.scalar(
            select(KpiDefinition).where(KpiDefinition.code == entry["code"])
        )
        target = entry.get("target_default")
        if existing:
            print(f"  exists KPI: {entry['code']}")
            continue
        session.add(
            KpiDefinition(
                code=entry["code"],
                name=entry["name"],
                category=entry["category"],
                unit=entry["unit"],
                applies_to_role=entry["applies_to_role"],
                target_default=Decimal(str(target)) if target is not None else None,
                direction=entry.get("direction", "higher_better"),
                description=entry.get("description"),
                source=entry.get("source", "auto"),
                is_active=True,
            )
        )
        print(f"  created KPI: {entry['code']}")


async def seed() -> None:
    async with async_session_factory() as session:
        await seed_users(session)
        await seed_chatbot_faq(session)
        await seed_notification_templates(session)
        await seed_kpi_definitions(session)
        await session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
