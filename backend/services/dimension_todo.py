"""维度待办清单管理器 — 从 Markdown 文件读取/写入待确认维度。"""

from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# 待办文件路径
TODO_FILE = Path(__file__).parent.parent.parent / 'docs' / 'dimension-todo.md'


class DimensionTodoManager:
    """管理维度待办清单的读写。"""

    def __init__(self, todo_file: Optional[Path] = None):
        self.todo_file = todo_file or TODO_FILE

    def add_pending(self, query_text: str, matched_column: str, matched_label: str,
                    sample_values: list, usage_count: int = 1):
        """添加新的待确认维度到「待确认」区域。"""
        if not self.todo_file.exists():
            self.todo_file.parent.mkdir(parents=True, exist_ok=True)
            self.todo_file.write_text('', encoding='utf-8')

        content = self.todo_file.read_text(encoding='utf-8')

        # 检查是否已存在（相同列名）
        if f'| {query_text} | {matched_column} |' in content:
            # 已存在，不重复添加
            return

        # 找到「待确认」表格的末尾
        pending_section = re.search(
            r'## 📋 待确认.*?\n(.*?)\n---',
            content, re.DOTALL
        )
        if not pending_section:
            return

        table_content = pending_section.group(1)

        # 如果是"(暂无)"占位行，替换它
        if '(暂无)' in table_content:
            table_content = ''

        # 添加新行
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        samples_str = ', '.join(sample_values[:3]) if sample_values else '-'
        new_row = f'| {query_text} | {matched_column} | {matched_label} | {samples_str} | {usage_count} | {now} |\n'

        updated_table = table_content + new_row

        # 替换原内容
        new_content = content.replace(
            pending_section.group(0),
            f'## 📋 待确认（系统自动发现）\n\n{updated_table}---'
        )

        self.todo_file.write_text(new_content, encoding='utf-8')

    def get_confirmed(self) -> list[dict]:
        """获取「确认待办」区域的所有条目。"""
        if not self.todo_file.exists():
            return []

        content = self.todo_file.read_text(encoding='utf-8')

        confirmed_section = re.search(
            r'## ✅ 确认待办.*?\n(.*?)\n---',
            content, re.DOTALL
        )
        if not confirmed_section:
            return []

        table_content = confirmed_section.group(1)

        # 解析表格行
        items = []
        for line in table_content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('| 用户查询') or line.startswith('| ---') or '(暂无)' in line:
                continue

            # 解析 markdown 表格行
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 4:
                items.append({
                    'query_text': cols[0],
                    'matched_column': cols[1],
                    'matched_label': cols[2],
                    'sample_values': cols[3].split(', ') if cols[3] != '-' else [],
                    'group_by_key': cols[4] if len(cols) > 4 and cols[4] else None,
                    'keywords': cols[5].split(', ') if len(cols) > 5 and cols[5] else None,
                })

        return items

    def move_to_processed(self, items_to_move: list[dict]):
        """将已处理的条目从「确认待办」移到「已处理」。"""
        if not self.todo_file.exists():
            return

        content = self.todo_file.read_text(encoding='utf-8')

        # 从「确认待办」中移除这些条目
        for item in items_to_move:
            row_pattern = f'| {item["query_text"]} | {item["matched_column"]} |'
            if row_pattern in content:
                # 找到并删除这一行
                lines = content.split('\n')
                lines = [l for l in lines if row_pattern not in l]
                content = '\n'.join(lines)

        # 添加到「已处理」区域
        processed_section = re.search(
            r'## ✅ 已处理.*?\n(.*?)\n---',
            content, re.DOTALL
        )
        if processed_section:
            table_content = processed_section.group(1)
            if '(暂无)' in table_content:
                table_content = ''

            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            for item in items_to_move:
                key = item.get('group_by_key') or item['matched_column']
                new_row = f'| {item["query_text"]} | {item["matched_column"]} | {item["matched_label"]} | {key} | {now} |\n'
                table_content += new_row

            new_content = content.replace(
                processed_section.group(0),
                f'## ✅ 已处理（系统自动归档）\n\n{table_content}---'
            )
            self.todo_file.write_text(new_content, encoding='utf-8')

    def get_stats(self) -> dict:
        """获取各区域的条目数量。"""
        if not self.todo_file.exists():
            return {'pending': 0, 'confirmed': 0, 'rejected': 0, 'processed': 0}

        content = self.todo_file.read_text(encoding='utf-8')

        def count_section(header: str) -> int:
            section = re.search(
                rf'## {re.escape(header)}.*?\n(.*?)\n---',
                content, re.DOTALL
            )
            if not section:
                return 0
            lines = [l for l in section.group(1).strip().split('\n')
                     if l.strip() and not l.startswith('| 用户') and not l.startswith('| ---')
                     and '(暂无)' not in l]
            return len(lines)

        return {
            'pending': count_section('📋 待确认'),
            'confirmed': count_section('✅ 确认待办'),
            'rejected': count_section('❌ 无需处理'),
            'processed': count_section('✅ 已处理'),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }


# 全局实例
todo_manager = DimensionTodoManager()
