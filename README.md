# ITSM 工单智能分析平台

基于 **FastAPI + Vue 3 + ECharts + Flue Agent + LLM** 的 IT 服务台工单数据智能分析平台。支持从 Excel 导入 ITSM 工单数据，通过自然语言对话自动生成多维度可视化报表和深度洞察。

## 功能特性

### 分析维度

| 类别 | 维度 | 图表 |
|------|------|------|
| 基础分布 | 状态 / 服务组 / 部门 / 来源渠道 / 业务系统 | 饼图 |
| 人员效能 | 责任人 TOP / 解决人处理量 | 横向柱状图 |
| 趋势分析 | 每周/每月工单量、SLA 达标率周趋势 | 折线图 |
| 故障根因 | 原因类别→故障分组→症状三层钻取、故障趋势 | 横向柱状图 + 折线图 |
| 重复挖掘 | 按故障原因 + 标题关键词双向去重 | 横向柱状图 |
| 症状聚类 | 常见症状→最佳解决方案推荐、平均解决耗时 | 横向柱状图 |
| 运维质量 | 退回率/挂起率/撤单率/SLA + 周趋势 | 横向柱状图 |
| 请求人分析 | 高频请求人/部门/机构/职务分布×性质交叉 | 横向柱状图 + 柱状图 |
| 性质趋势 | 各类性质占比饼图 + 周趋势堆叠面积图 | 饼图 + 折线图 |
| 满意度 | 服务态度/技术水平/响应时效评分 | 柱状图 |

### 智能分析

- **自然语言交互** — 支持中文提问，如"哪些故障反复出现？""运维质量如何？"
- **Flue Agent 意图识别** — 基于 Markdown Agent 定义的 HTTP Agent Harness，替代传统 LLM 意图解析
- **LLM 深度分析** — 支持 DeepSeek / OpenAI / Claude / 本地模型等多种 LLM 后端
- **自动洞察** — 规则驱动的数据洞察卡片（SLA 预警/重复告警/偏差检测）
- **多轮对话** — 对话上下文累积，筛选条件可持续传递

### 报表导出

- HTML 格式可视化报告
- Excel 数据明细导出

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy (async) |
| 数据处理 | Pandas + OpenPyXL |
| 意图引擎 | Flue Agent (Node.js + HTTP Agent Harness) |
| 前端 | Vue 3 + Vite + Pinia + Vue Router |
| 图表 | ECharts 5 |
| LLM | DeepSeek / OpenAI / Claude / vLLM 兼容 |
| 认证 | JWT（支持本地 + IAM） |

## 快速开始

### 1. 环境准备

```bash
# Python 3.10+
pip install -r requirements.txt

# Node.js 18+（Flue Agent + 前端）
cd flue-agent && npm install
cd ../frontend && npm install
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，最少配置：

```env
# LLM API（必填）
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-你的API密钥

# 启用 Flue Agent（建议开启）
FLUE_AGENT_ENABLED=True

# 数据源
TICKET_EXCEL_PATH=./data.xlsx

# JWT 密钥
JWT_SECRET=改成随机字符串
```

### 3. 启动服务

```bash
# 终端 1：启动 Flue Agent（端口 3002）
cd flue-agent && node agent-server.js

# 终端 2：启动后端（端口 8000）
python run_backend.py

# 终端 3：启动前端（端口 5173）
cd frontend && npm run dev
```

打开 `http://localhost:5173`，默认管理员账号 `admin` / `admin123`。

> 详细启动指引见 [QUICK_START.md](./QUICK_START.md)。

## 项目结构

```
├── backend/                          # FastAPI 后端
│   ├── main.py                       # 应用入口 + 生命周期管理
│   ├── config.py                     # 环境配置 (Pydantic Settings)
│   ├── database.py                   # 数据库连接
│   ├── models.py                     # SQLAlchemy 数据模型
│   ├── schemas.py                    # Pydantic 请求/响应模型
│   ├── auth.py                       # JWT 认证
│   ├── dependencies.py               # FastAPI 依赖注入
│   ├── utils.py                      # 工具函数
│   ├── routers/                      # API 路由
│   │   ├── chat.py                   # Agent 对话
│   │   ├── auth.py                   # 认证
│   │   ├── analytics.py              # 数据分析
│   │   ├── reports.py                # 报表管理
│   │   ├── datasources.py            # 数据源上传
│   │   └── skills.py                 # Skill 管理
│   ├── services/                     # 业务服务
│   │   ├── ticket_processor.py       # 工单数据处理
│   │   ├── skill_engine.py           # Skill 执行
│   │   ├── intent_parser.py          # 意图解析
│   │   ├── chart_renderer.py         # ECharts option 生成
│   │   ├── export_service.py         # HTML/Excel 导出
│   │   ├── conversation_manager.py   # 对话管理
│   │   ├── complaint_processor.py    # 客诉处理（兼容）
│   │   └── report_generator.py       # 报表生成
│   └── llm/                          # LLM Provider
│       ├── base.py                   # 抽象基类
│       ├── openai_provider.py        # OpenAI 兼容协议
│       ├── claude_provider.py        # Anthropic Claude
│       └── flue_provider.py          # Flue Agent HTTP 调用
│
├── frontend/                         # Vue 3 前端
│   └── src/
│       ├── views/                    # 页面
│       │   ├── Chat.vue              # 对话主界面
│       │   ├── Login.vue             # 登录页
│       │   ├── ReportList.vue        # 报表列表
│       │   ├── ReportDetail.vue      # 报表详情
│       │   ├── DataSourceManage.vue  # 数据源管理
│       │   └── SkillManage.vue       # Skill 管理
│       ├── components/               # 组件
│       │   ├── ChartRenderer.vue     # ECharts 渲染
│       │   ├── ChatMessage.vue       # 消息气泡
│       │   ├── ChatInput.vue         # 输入框
│       │   ├── KPICard.vue           # KPI 卡片
│       │   └── LoadingIndicator.vue  # 加载指示器
│       ├── store/                    # Pinia 状态
│       └── router/                   # 路由
│
├── flue-agent/                       # Flue Agent (Node.js)
│   ├── agent-server.js               # HTTP Agent Server
│   ├── agents/                       # Markdown Agent 定义
│   │   └── intent-router.md          # 意图路由 Agent
│   └── package.json
│
├── internal/                         # Harness 调度层
│   ├── router/                       # 路由
│   │   ├── agent_registry.py         # Agent 注册中心
│   │   ├── skill_router.py           # Skill 调度
│   │   └── harness_router.py         # HTTP 端点
│   ├── tools/                        # MCP 工具
│   │   ├── base.py                   # 工具基类
│   │   ├── ticket_query.py           # 工单查询
│   │   ├── chart_render.py           # 图表渲染
│   │   ├── report_export.py          # 报表导出
│   │   └── complaint_query.py        # 客诉查询
│   ├── context/                      # 上下文管理
│   │   ├── manager.py
│   │   └── compressor.py
│   ├── session/                      # 会话管理
│   │   ├── manager.py
│   │   └── models.py
│   ├── memory/                       # 记忆存储
│   │   └── store.py
│   └── sandbox/                      # 沙箱执行
│       └── executor.py
│
├── harness/skills/                   # Skill 定义 (SKILL.md)
│   ├── complaint_analysis/
│   ├── data_query/
│   └── report_export/
│
├── .claude/agents/                   # Claude Agent 角色定义
│   ├── complaint-analyst.md
│   ├── data-researcher.md
│   ├── report-builder.md
│   └── ticket-analyst.md
│
├── .env.example                      # 环境变量模板
├── run_backend.py                    # 后端启动脚本
├── QUICK_START.md                    # 详细启动指南
└── scripts/                          # 工具脚本
    ├── init_db.py                    # 初始化数据库
    └── create_admin.py               # 创建管理员用户
```

## 架构

```
┌─────────────┐     HTTP      ┌──────────────────┐     OpenAI API     ┌──────────────┐
│  前端        │ ────────────→ │  后端 FastAPI     │ ────────────────→ │  LLM API     │
│  Vue 3       │ ←──────────── │  (端口 8000)      │ ←──────────────── │  (DeepSeek等) │
│  (端口 5173)  │              │                    │                   │              │
└─────────────┘               └──────────────────┘                   └──────────────┘
                                       │
                                       │ HTTP (意图识别/闲聊)
                                       ↓
                               ┌──────────────────┐     OpenAI API     ┌──────────────┐
                               │  Flue Agent      │ ────────────────→ │  LLM API     │
                               │  Node.js         │ ←──────────────── │  (DeepSeek等) │
                               │  (端口 3002)      │                   │              │
                               └──────────────────┘                   └──────────────┘
```

## 支持的 LLM 提供商

| 提供商 | 协议 | 配置示例 |
|--------|------|----------|
| **DeepSeek** | OpenAI 兼容 | `base_url=https://api.deepseek.com`, `model=deepseek-chat` |
| **OpenAI** | OpenAI | `base_url=https://api.openai.com/v1`, `model=gpt-4o-mini` |
| **Anthropic Claude** | Anthropic | `provider=claude`, `model=claude-sonnet-4-6-20250514` |
| **vLLM/Ollama 本地** | OpenAI 兼容 | `base_url=http://localhost:8080/v1`, `model=qwen2.5-7b-instruct` |

## 支持的 ITSM 工单字段

系统自动映射标准 ITSM 字段（中文列名 → 英文变量），覆盖 48 个字段，包括：编号、标题、状态、责任人、服务组、业务系统、故障原因、症状、SLA 百分比、满意度评分等。

## License

MIT
