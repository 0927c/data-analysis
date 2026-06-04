"""MemoryStore: 文件 KV 存储 + markdown agent context（AGENTS.md 模式）。"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


class MemoryStore:
    """
    轻量级持久记忆层：
    - KV 存储：JSON 文件（快速读写，人类可读）
    - Agent Context: markdown 文件（便于人工检查和调试）
    Phase 1 不使用向量检索，仅精确 key 匹配。
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self._base = base_dir or Path("backend/data/memory")
        self._base.mkdir(parents=True, exist_ok=True)
        self._kv_dir = self._base / "kv"
        self._kv_dir.mkdir(exist_ok=True)

    def get(self, key: str) -> Optional[str]:
        """获取值，不存在返回 None。"""
        path = self._kv_dir / f"{key}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("value")

    def set(self, key: str, value: str, metadata: Optional[dict] = None):
        """设置值，附带可选元数据。"""
        path = self._kv_dir / f"{key}.json"
        path.write_text(
            json.dumps({"value": value, "metadata": metadata or {}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete(self, key: str):
        """删除值。"""
        path = self._kv_dir / f"{key}.json"
        if path.exists():
            path.unlink()

    def list_keys(self, prefix: str = "") -> list[str]:
        """列出所有 key，支持前缀过滤。"""
        results = []
        for f in self._kv_dir.glob("*.json"):
            name = f.stem
            if name.startswith(prefix):
                results.append(name)
        return sorted(results)

    def save_agent_context(self, agent_id: str, context: dict):
        """将 agent 上下文保存为 markdown 文件。"""
        path = self._base / f"{agent_id}_context.md"
        lines = [f"# {agent_id} Context\n"]
        for k, v in context.items():
            lines.append(f"## {k}\n{v}\n")
        path.write_text("\n".join(lines), encoding="utf-8")

    def load_agent_context(self, agent_id: str) -> dict:
        """从 markdown 文件加载 agent 上下文。"""
        path = self._base / f"{agent_id}_context.md"
        if not path.exists():
            return {}
        content = path.read_text(encoding="utf-8")
        result = {}
        current_key = None
        for line in content.split("\n"):
            if line.startswith("## "):
                current_key = line[3:].strip()
                result[current_key] = ""
            elif current_key and line.strip():
                result[current_key] += line + "\n"
        return result
