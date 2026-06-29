"""维度映射覆盖层 — 支持运行时动态添加新的分析维度，无需重启。

 Approved 的维度从 DB 加载并合并到 INTENT_GROUP_MAP。
 新维度也写入 overrides 文件以便重启后仍可用。
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

# overrides 文件路径
OVERRIDES_FILE = Path(__file__).parent.parent / 'data' / 'dimension_overrides.json'

# 维度 → 列名映射（从 DB approved 记录 + overrides 文件加载）
# key: group_by 标识, value: DataFrame 列名
DIMENSION_COLUMN_MAP: dict[str, str] = {}

# 中文关键词 → group_by 标识（从 DB approved 记录 + overrides 文件加载）
# 用户说"按紧急程度" → 匹配到 "urgency" → 对应列 "urgency_level"
KEYWORD_DIMENSION_MAP: dict[str, str] = {}


def load_overrides():
    """启动时加载 overrides 文件中的维度映射。"""
    global DIMENSION_COLUMN_MAP, KEYWORD_DIMENSION_MAP
    if OVERRIDES_FILE.exists():
        try:
            data = json.loads(OVERRIDES_FILE.read_text(encoding='utf-8'))
            DIMENSION_COLUMN_MAP.update(data.get('dimension_columns', {}))
            KEYWORD_DIMENSION_MAP.update(data.get('keyword_dimensions', {}))
        except (json.JSONDecodeError, OSError):
            pass


def save_overrides():
    """将当前覆盖层写入文件（批准新维度时调用）。"""
    OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'dimension_columns': DIMENSION_COLUMN_MAP,
        'keyword_dimensions': KEYWORD_DIMENSION_MAP,
    }
    OVERRIDES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def approve_dimension(
    group_by_key: str,
    column_name: str,
    keywords: list[str],
):
    """批准一个新维度：注册映射并持久化。

    Args:
        group_by_key: 维度标识（如 "urgency"）
        column_name: DataFrame 列名（如 "urgency_level"）
        keywords: 中文触发词列表（如 ["紧急程度", "优先级", "urgency"]）
    """
    DIMENSION_COLUMN_MAP[group_by_key] = column_name
    for kw in keywords:
        KEYWORD_DIMENSION_MAP[kw.lower()] = group_by_key
    save_overrides()


def reject_dimension(group_by_key: str):
    """拒绝一个维度：从覆盖层中移除。"""
    DIMENSION_COLUMN_MAP.pop(group_by_key, None)
    # 移除指向该 key 的所有关键词
    to_remove = [kw for kw, key in KEYWORD_DIMENSION_MAP.items() if key == group_by_key]
    for kw in to_remove:
        del KEYWORD_DIMENSION_MAP[kw]
    save_overrides()


def resolve_dimension(keyword: str) -> Optional[str]:
    """根据用户输入的关键词，查找对应的 group_by key。

    优先级：覆盖层关键词 > 预设 INTENT_GROUP_MAP
    """
    kw_lower = keyword.lower()
    # 先查覆盖层（精确 + 子串）
    if kw_lower in KEYWORD_DIMENSION_MAP:
        return KEYWORD_DIMENSION_MAP[kw_lower]
    for kw, key in KEYWORD_DIMENSION_MAP.items():
        if kw in kw_lower or kw_lower in kw:
            return key
    return None


def get_column_for_dimension(group_by_key: str) -> Optional[str]:
    """获取 group_by key 对应的 DataFrame 列名。

    优先级：覆盖层 > 预设 ANALYSIS_DIMENSIONS
    """
    if group_by_key in DIMENSION_COLUMN_MAP:
        return DIMENSION_COLUMN_MAP[group_by_key]
    return None


# 启动时自动加载
load_overrides()
