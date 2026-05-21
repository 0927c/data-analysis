"""创建默认管理员账号。"""
import asyncio
from backend.auth import hash_password
from backend.database import async_session
from backend.models import User
from sqlalchemy import select


async def main():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                username="admin",
                password_hash=hash_password("admin123"),
                display_name="管理员",
                role="admin",
                auth_provider="local",
            )
            db.add(user)
            await db.commit()
            print("Admin user created: admin / admin123")
        else:
            print("Admin already exists")


if __name__ == "__main__":
    asyncio.run(main())
