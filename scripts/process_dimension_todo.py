#!/usr/bin/env python
"""处理维度待办清单 — 读取「确认待办」区域，批准维度，更新映射表。

用法:
    python scripts/process_dimension_todo.py          # 处理所有确认待办
    python scripts/process_dimension_todo.py --dry-run  # 仅预览，不实际处理
"""

from __future__ import annotations
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.dimension_todo import todo_manager
from backend.services.dimension_overrides import approve_dimension


def process_confirmed(dry_run: bool = False):
    """处理「确认待办」区域的所有条目。"""
    items = todo_manager.get_confirmed()

    if not items:
        print("✅ 没有待处理的确认维度。")
        return

    print(f"📋 发现 {len(items)} 个待处理维度:\n")

    for item in items:
        query = item['query_text']
        column = item['matched_column']
        label = item['matched_label']
        key = item.get('group_by_key') or column
        keywords = item.get('keywords') or [query]

        print(f"  维度: {label} ({column})")
        print(f"  group_by key: {key}")
        print(f"  关键词: {keywords}")
        print(f"  示例值: {item.get('sample_values', [])}")
        print()

        if not dry_run:
            # 批准维度
            approve_dimension(key, column, keywords)
            print(f"  ✅ 已批准并加入映射表\n")

    if not dry_run:
        # 移到已处理区域
        todo_manager.move_to_processed(items)
        print("✅ 所有确认维度已处理并归档。")
    else:
        print("（预览模式，未实际处理）")

    # 打印统计
    stats = todo_manager.get_stats()
    print(f"\n📊 统计:")
    print(f"  待确认: {stats['pending']} 条")
    print(f"  确认待办: {stats['confirmed']} 条")
    print(f"  无需处理: {stats['rejected']} 条")
    print(f"  已处理: {stats['processed']} 条")
    print(f"  最后更新: {stats['last_updated']}")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    process_confirmed(dry_run=dry_run)
