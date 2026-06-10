"""创建测试账号。各账号数据通过 user_id 外键天然隔离。"""

import asyncio
from backend.auth import hash_password
from backend.database import async_session
from backend.models import User
from sqlalchemy import select

TEST_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "display_name": "系统管理员",
        "role": "admin",
    },
    {
        "username": "zhangwei",
        "password": "test1234",
        "display_name": "张伟（运维主管）",
        "role": "user",
    },
    {
        "username": "lina",
        "password": "test1234",
        "display_name": "李娜（服务台）",
        "role": "user",
    },
    {
        "username": "wangfang",
        "password": "test1234",
        "display_name": "王芳（开发工程师）",
        "role": "user",
    },
    {
        "username": "liuqiang",
        "password": "test1234",
        "display_name": "刘强（安全审计）",
        "role": "user",
    },
]


async def main():
    async with async_session() as db:
        for u in TEST_USERS:
            result = await db.execute(select(User).where(User.username == u["username"]))
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  跳过 {u['username']}（已存在）")
                continue

            user = User(
                username=u["username"],
                password_hash=hash_password(u["password"]),
                display_name=u["display_name"],
                role=u["role"],
                auth_provider="local",
            )
            db.add(user)
            await db.commit()
            print(f"  创建成功: {u['username']} / {u['password']}  ({u['display_name']})")

    print("\n测试账号列表：")
    print("-" * 60)
    for u in TEST_USERS:
        print(f"  {u['username']:12s} / {u['password']:10s}  {u['display_name']}")
    print("-" * 60)
    print("\n数据隔离说明：")
    print("  - 每个用户的会话(session)、消息(message)、报表(report)")
    print("  - 用户偏好(user_preference)、分析历史(analysis_history)")
    print("  - 均通过 user_id 外键关联，互相不可见")
    print("  - 数据源(datasources)全局共享，上传后所有用户可分析")


if __name__ == "__main__":
    asyncio.run(main())
