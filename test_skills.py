from pathlib import Path
from internal.router.skill_router import SkillRouter
from internal.router.agent_registry import AgentRegistry

registry = AgentRegistry(agents_dir=Path(".claude/agents"))
registry.load_all()
router = SkillRouter(registry, [])

print(f"=== Loaded {len(router.get_all_skills())} skills ===")
for s in router.get_all_skills():
    print(f"  {s.id} | {s.name} | priority={s.priority}")

print(f"\n=== Loaded {len(registry.get_all_agents())} agents ===")
for a in registry.get_all_agents():
    print(f"  {a.id} | {a.name}")

print("\n=== Routing tests ===")
tests = [
    "各产品线投诉量",
    "帮我查询具体数据",
    "导出Excel报告",
    "投诉原因分布",
    "排名前十的不良类型",
]
for msg in tests:
    result = router.route(msg)
    skill_id = result["skill_id"] or "(none)"
    agent_id = result["agent_id"]
    tools = [t.name for t in result["allowed_tools"]]
    print(f"  Q: {msg}")
    print(f"    -> skill={skill_id}, agent={agent_id}")
    print(f"    -> tools={tools}")
