"""SkillRouter: 关键词路由 → Agent 选择 → Skill 匹配 → 工具分发。"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from internal.router.agent_registry import AgentRegistry, AgentDefinition
from internal.tools.base import MCPTool


@dataclass
class SkillDefinition:
    """从 .claude/skills/*.md 解析的技能定义。"""
    id: str
    name: str
    description: str
    category: str
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    supported_tools: list[str] = field(default_factory=list)
    routing_keywords: list[str] = field(default_factory=list)
    enabled: bool = True
    priority: int = 99  # 越小优先级越高
    body: str = ""

    @classmethod
    def from_file(cls, filepath: Path) -> "SkillDefinition":
        content = filepath.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid skill file: {filepath}")

        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2).strip()

        return cls(
            id=frontmatter.get("id", filepath.stem),
            name=frontmatter.get("name", filepath.stem),
            description=frontmatter.get("description", ""),
            category=frontmatter.get("category", "general"),
            input_schema=frontmatter.get("input_schema", {}),
            output_schema=frontmatter.get("output_schema", {}),
            supported_tools=frontmatter.get("supported_tools", []),
            routing_keywords=frontmatter.get("routing_keywords", []),
            enabled=frontmatter.get("enabled", True),
            priority=frontmatter.get("priority", 99),
            body=body,
        )


class SkillRouter:
    """
    统一路由层：
    1. 加载 .claude/skills/*.md 技能定义
    2. 加载 .claude/agents/*.md 角色定义
    3. 根据用户消息关键词匹配最优 Skill → 对应 Agent → 工具列表
    """

    def __init__(
        self,
        registry: AgentRegistry,
        tools: list[MCPTool],
        skills_dir: Optional[Path] = None,
        default_agent_id: str = "complaint-analyst",
    ):
        self._registry = registry
        self._tool_map: dict[str, MCPTool] = {t.name: t for t in tools}
        self._default_agent_id = default_agent_id

        # 加载技能定义（支持 harness/skills/ 子目录结构，每个子目录包含 SKILL.md）
        self._skills_dir = skills_dir or Path("harness/skills")
        self._skills: dict[str, SkillDefinition] = {}
        self._skill_keyword_index: dict[str, str] = {}  # keyword -> skill_id
        self._load_skills()

    def _load_skills(self):
        """从 skills 目录加载所有技能定义。
        支持两种结构：
        1. 根目录直接放 *.md 文件
        2. 子目录结构：{skill-name}/SKILL.md
        """
        if not self._skills_dir.exists():
            self._skills_dir.mkdir(parents=True, exist_ok=True)
            return

        # 方式 1: 子目录结构 — 每个子目录下的 SKILL.md
        for subdir in self._skills_dir.iterdir():
            if subdir.is_dir():
                skill_file = subdir / "SKILL.md"
                if skill_file.exists():
                    self._load_skill_file(skill_file)
                # 也检查子目录下是否有其他 .md 文件
                for md_file in subdir.glob("*.md"):
                    if md_file.name != "SKILL.md":
                        self._load_skill_file(md_file)

        # 方式 2: 根目录直接放 *.md
        for md_file in self._skills_dir.glob("*.md"):
            self._load_skill_file(md_file)

    def _load_skill_file(self, filepath: Path):
        """加载单个技能文件。"""
        try:
            skill = SkillDefinition.from_file(filepath)
            if skill.enabled:
                self._skills[skill.id] = skill
                for kw in skill.routing_keywords:
                    self._skill_keyword_index[kw.lower()] = skill.id
        except Exception as e:
            print(f"Warning: Failed to load skill from {filepath}: {e}")

    # ─── 路由 ────────────────────────────────────────────────

    def route(self, user_message: str) -> dict:
        """
        路由流程：
        1. 根据关键词匹配 Skill
        2. 从 Skill 获取需要的工具列表
        3. 根据关键词匹配 Agent
        4. 返回路由决策
        """
        # Step 1: 匹配 Skill
        skill_id = self._route_skill(user_message)

        # Step 2: 匹配 Agent
        agent_id = self._registry.route_by_keywords(user_message)
        if agent_id is None:
            agent_id = self._default_agent_id

        agent = self._registry.get_agent(agent_id)
        if agent is None:
            agent_id = self._default_agent_id
            agent = self._registry.get_agent(agent_id)

        # Step 3: 确定工具列表（Agent 的 allowed_tools 交集）
        allowed_tools = [
            self._tool_map[name]
            for name in agent.allowed_tools
            if name in self._tool_map
        ]

        return {
            "agent_id": agent_id,
            "agent": agent,
            "skill_id": skill_id,
            "allowed_tools": allowed_tools,
            "tool_specs": [t.to_spec() for t in allowed_tools],
        }

    def _route_skill(self, user_message: str) -> Optional[str]:
        """根据关键词匹配 Skill，按 priority 排序选最优。"""
        msg_lower = user_message.lower()
        matched = []
        for kw, skill_id in self._skill_keyword_index.items():
            if kw in msg_lower:
                matched.append((self._skills[skill_id].priority, skill_id))

        if not matched:
            return None

        # 按 priority 升序（越小越优先）
        matched.sort()
        return matched[0][1]

    # ─── 查询 ────────────────────────────────────────────────

    def get_available_skills(self) -> dict:
        """返回 Skill 列表（合并 Agent 和 Skill 定义）。"""
        agent_skills = [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "capabilities": a.capabilities,
                "enabled": a.enabled,
            }
            for a in self._registry.get_all_agents()
        ]
        skill_defs = [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "priority": s.priority,
                "enabled": s.enabled,
            }
            for s in self._skills.values()
        ]
        return {
            "agents": agent_skills,
            "skills": skill_defs,
        }

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def get_all_skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """按名称获取工具。"""
        return self._tool_map.get(tool_name)

    def get_all_tools(self) -> list[MCPTool]:
        return list(self._tool_map.values())

    def get_all_tool_specs(self) -> list[dict]:
        return [t.to_spec() for t in self._tool_map.values()]
