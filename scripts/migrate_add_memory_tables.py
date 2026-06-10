"""数据库迁移脚本：新增长记忆机制相关表，扩展已有表。

用法：
    python scripts/migrate_add_memory_tables.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect as sa_inspect
from backend.database import engine, Base
from backend.models import UserPreference, AnalysisHistory, DatasourceMetadata  # noqa: F401


def _check_and_alter(sync_conn):
    """在同步连接中检查并添加新列。"""
    inspector = sa_inspect(sync_conn)
    messages = []

    # sessions 表新增 context_summary 列
    columns = [col["name"] for col in inspector.get_columns("sessions")]
    if "context_summary" not in columns:
        sync_conn.execute(text("ALTER TABLE sessions ADD COLUMN context_summary TEXT"))
        messages.append("[OK] sessions 表新增 context_summary 列")
    else:
        messages.append("  sessions.context_summary 已存在，跳过")

    # datasources 表新增 file_path 列
    columns = [col["name"] for col in inspector.get_columns("datasources")]
    if "file_path" not in columns:
        sync_conn.execute(text("ALTER TABLE datasources ADD COLUMN file_path TEXT"))
        messages.append("[OK] datasources 表新增 file_path 列")
    else:
        messages.append("  datasources.file_path 已存在，跳过")

    return messages


async def migrate():
    """执行迁移：创建新表 + 为已有表添加新列。"""
    async with engine.begin() as conn:
        # 1. 创建新表（如果不存在）
        await conn.run_sync(Base.metadata.create_all)
        print("[OK] 新表已创建（user_preferences, analysis_history, datasource_metadata）")

        # 2. 为已有表添加新列（在 run_sync 中完成）
        messages = await conn.run_sync(_check_and_alter)
        for msg in messages:
            print(msg)

    print("\n迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())
