"""AgentRegistry: 从 .claude/agents/*.md 解析智能体定义，提供发现和路由。"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class AgentDefinition:
    """从 .claude/agents/*.md 文件解析的智能体定义。"""
    id: str
    name: str
    description: str
    role: str
    capabilities: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    routing_keywords: list[str] = field(default_factory=list)
    system_prompt: str = ""
    enabled: bool = True

    @classmethod
    def from_file(cls, filepath: Path) -> "AgentDefinition":
        content = filepath.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid agent file: {filepath}")

        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2).strip()

        return cls(
            id=frontmatter.get("id", filepath.stem),
            name=frontmatter.get("name", filepath.stem),
            description=frontmatter.get("description", ""),
            role=frontmatter.get("role", ""),
            capabilities=frontmatter.get("capabilities", []),
            allowed_tools=frontmatter.get("allowed_tools", []),
            routing_keywords=frontmatter.get("routing_keywords", []),
            system_prompt=body,
            enabled=frontmatter.get("enabled", True),
        )


class AgentRegistry:
    """智能体发现、加载和路由。"""

    def __init__(self, agents_dir: Optional[Path] = None):
        self._agents_dir = agents_dir or Path(".claude/agents")
        self._agents: dict[str, AgentDefinition] = {}
        self._keyword_index: dict[str, str] = {}  # keyword -> agent_id

    def load_all(self):
        """加载目录下所有 Agent 定义。"""
        if not self._agents_dir.exists():
            self._agents_dir.mkdir(parents=True, exist_ok=True)
            return

        for filepath in self._agents_dir.glob("*.md"):
            try:
                agent = AgentDefinition.from_file(filepath)
                if agent.enabled:
                    self._agents[agent.id] = agent
                    for kw in agent.routing_keywords:
                        self._keyword_index[kw.lower()] = agent.id
            except Exception as e:
                print(f"Warning: Failed to load agent from {filepath}: {e}")

    def get_agent(self, agent_id: str) -> Optional[AgentDefinition]:
        return self._agents.get(agent_id)

    def get_all_agents(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def route_by_keywords(self, user_message: str) -> Optional[str]:
        """根据关键词匹配用户消息，返回 agent_id 或 None。"""
        msg_lower = user_message.lower()
        for kw, agent_id in self._keyword_index.items():
            if kw in msg_lower:
                return agent_id
        return None

    def get_tool_names(self, agent_id: str) -> list[str]:
        agent = self._agents.get(agent_id)
        return agent.allowed_tools if agent else []
