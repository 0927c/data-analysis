"""数据库初始化 + 种子数据脚本。

用法: python -m scripts.init_db
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.config import settings
from backend.database import engine, Base, async_session
from backend.models import User, DataSource, Skill
from backend.auth import hash_password


async def init_db():
    """创建所有表并插入种子数据。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 设置 WAL 模式提升并发读性能
    async with async_session() as session:
        await session.execute(text("PRAGMA journal_mode=WAL"))
        await session.execute(text("PRAGMA busy_timeout=5000"))
        await session.commit()

    async with async_session() as session:
        # 检查是否已有管理员
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.role == "admin"))
        existing_admin = result.scalar_one_or_none()

        if not existing_admin:
            # 创建默认管理员
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                display_name="系统管理员",
                role="admin",
                auth_provider="local",
            )
            session.add(admin)
            print("✓ 创建默认管理员: admin / admin123")

            # 创建默认测试用户
            test_user = User(
                username="user",
                password_hash=hash_password("user123"),
                display_name="测试用户",
                role="user",
                auth_provider="local",
            )
            session.add(test_user)
            print("✓ 创建默认用户: user / user123")

        # 检查是否已有默认数据源
        result = await session.execute(select(DataSource).where(DataSource.name == "工单分析"))
        existing_ds = result.scalar_one_or_none()

        if not existing_ds:
            ds = DataSource(
                name="工单分析",
                type="excel",
                config='{"path": "' + settings.TICKET_EXCEL_PATH + '"}',
                status="active",
                record_count=0,
            )
            session.add(ds)
            print("✓ 创建默认数据源: 工单分析")

        # 检查是否已有默认 skill
        result = await session.execute(select(Skill).where(Skill.name == "工单分析"))
        existing_skill = result.scalar_one_or_none()

        if not existing_skill:
            skill = Skill(
                name="工单分析",
                description="支持按状态、服务组、故障原因等多维度分析工单数据",
                enabled=True,
                supported_chart_types='["bar", "pie", "stacked_bar", "horizontal_bar", "rose"]',
            )
            session.add(skill)
            print("✓ 创建默认 Skill: 工单分析")

        await session.commit()

    # 重命名旧的"客诉数据"/"客诉分析"记录（如果存在）
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(DataSource).where(DataSource.name == "客诉数据"))
        old_ds = result.scalar_one_or_none()
        if old_ds:
            old_ds.name = "工单分析"
            print("✓ 重命名数据源: 客诉数据 -> 工单分析")
        result = await session.execute(select(Skill).where(Skill.name == "客诉分析"))
        old_skill = result.scalar_one_or_none()
        if old_skill:
            old_skill.name = "工单分析"
            print("✓ 重命名 Skill: 客诉分析 -> 工单分析")
        await session.commit()

    print("\n✓ 数据库初始化完成")
    print(f"  数据库路径: {settings.DATABASE_URL}")
    print(f"  数据源路径: {settings.TICKET_EXCEL_PATH}")


if __name__ == "__main__":
    asyncio.run(init_db())
