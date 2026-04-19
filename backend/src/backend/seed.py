import asyncio

from sqlalchemy import select

from src.backend.auth import hash_password
from src.backend.db.models import User
from src.backend.db.session import async_session_factory

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
        "banner_id": "L00001",
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


async def seed() -> None:
    async with async_session_factory() as session:
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

        await session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
