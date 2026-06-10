"""数据源切换检测 — 从自然语言中识别切换数据源的意图。"""

from __future__ import annotations
from typing import Optional


def detect_datasource_switch(message: str, available_datasources: list[dict]) -> Optional[int]:
    """检测用户消息中的数据源切换意图。

    Args:
        message: 用户消息
        available_datasources: [{"id": int, "name": str, "record_count": int}, ...]

    Returns:
        匹配到的 datasource_id，未匹配返回 None
    """
    if not available_datasources or not message:
        return None

    msg = message.strip()

    # 1. 检测切换关键词
    switch_keywords = ['切换到', '换成', '改用', '用', '切到']
    has_switch_intent = any(kw in msg for kw in switch_keywords)

    if not has_switch_intent:
        return None

    # 2. 精确匹配数据源名称
    for ds in available_datasources:
        name = ds.get('name', '')
        if name and name in msg:
            return ds['id']

    # 3. 模糊匹配：去掉"切换到"等前缀后匹配
    for kw in switch_keywords:
        if kw in msg:
            remainder = msg.split(kw, 1)[1].strip()
            # 尝试匹配数据源名称（取前几个字符）
            for ds in available_datasources:
                name = ds.get('name', '')
                if name and (remainder.startswith(name) or name.startswith(remainder[:4])):
                    return ds['id']

    # 4. 序号匹配："第一个" "第二个" "最后一个"
    for i, ds in enumerate(available_datasources):
        ordinal_patterns = [
            f'第{i + 1}个',
            f'第{i + 1}个数据源',
            f'第{i + 1}个文件',
        ]
        for pat in ordinal_patterns:
            if pat in msg:
                return ds['id']

    if '最后一个' in msg or '最新的' in msg:
        return available_datasources[-1]['id']

    return None


def resolve_datasource_reference(message: str, available_datasources: list[dict]) -> Optional[str]:
    """检测消息中模糊的数据源引用（如"之前的数据""上次的文件"）。

    Returns:
        引用类型："previous" / "latest" / None
    """
    if not message:
        return None

    previous_refs = ['之前的', '上次的', '以前的', '刚才的', '前面的']
    latest_refs = ['最新的', '最近的', '最后上传的', '新上传的']

    for ref in previous_refs:
        if ref in message:
            return "previous"

    for ref in latest_refs:
        if ref in message:
            return "latest"

    return None
