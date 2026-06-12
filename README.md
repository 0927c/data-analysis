# ITSM 工单智能分析平台

基于 **FastAPI + Vue 3 + ECharts + Flue Agent + LLM** 的 IT 服务台工单数据智能分析平台。支持从 Excel 导入 ITSM 工单数据，通过自然语言对话自动生成多维度可视化报表和深度洞察。

## 核心特性

### 智能分析

- **自然语言交互** — 支持中文提问，如"哪些故障反复出现？"
- **日期智能识别** — 自动提取"五月份""上个月""最近一周""2026年3月"等时间范围
- **Flue Agent 意图识别** — 基于 Markdown Agent 定义的 HTTP Agent Harness，支持 LLM + 规则双引擎
- **LLM 深度分析** — 支持 DeepSeek / OpenAI / Claude / 本地模型等多种 LLM 后端
- **自动洞察** — 规则驱动的数据洞察卡片（SLA 预警 / 重复告警 / 偏差检测）

### 长记忆机制

- **用户偏好记忆** — 记住常用分析维度、筛选条件，自动推荐
- **分析历史记忆** — 保存每次分析结论，支持跨会话检索引用（"刚才那个分析"）
- **数据源元数据记忆** — 上传时自动提取字段结构、数据质量报告
- **对话上下文增强** — 跨轮引用检测，支持"上次的结果""之前的分析"等自然语言

### 数据源管理

- **两阶段上传** — 先预览字段映射（自动识别 + 置信度评分），确认后再导入
- **多数据源切换** — 对话中自然语言切换（"切换到 XX 数据源"）或 UI 点击切换
- **自定义字段映射** — 支持非标 Excel 列名映射到系统字段
- **元数据自动提取** — 自动统计字段类型、空值率、关键分布、数据质量指标

### 报表导出

- HTML 格式可视化报告（内嵌 ECharts 图表）
- Excel 数据明细导出（多 Sheet）

## 分析维度

| 类别 | 维度 | 图表 |
|------|------|------|
| 基础分布 | 状态 / 服务组 / 部门 / 来源渠道 / 业务系统 | 饼图 |
| 人员效能 | 责任人 TOP / 解决人处理量 | 横向柱状图 |
| 趋势分析 | 每周 / 每月工单量、SLA 达标率周趋势 | 折线图 |
| 故障根因 | 原因类别 → 故障分组 → 症状三层钻取、故障趋势 | 横向柱状图 + 折线图 |
| 重复挖掘 | 按故障原因 + 标题关键词双向去重 | 横向柱状图 |
| 症状聚类 | 常见症状 → 最佳解决方案推荐、平均解决耗时 | 横向柱状图 |
| 运维质量 | 退回率 / 挂起率 / 撤单率 / SLA + 周趋势 | 横向柱状图 |
| 请求人分析 | 高频请求人 / 部门 / 机构 / 职务分布 × 性质交叉 | 横向柱状图 + 柱状图 |
| 性质趋势 | 各类性质占比饼图 + 周趋势堆叠面积图 | 饼图 + 折线图 |
| 满意度 | 服务态度 / 技术水平 / 响应时效评分 | 柱状图 |

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
| 认证 | JWT |

## 快速开始

### 1. 环境准备

```bash
# Python 3.8+
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

# 长记忆（默认开启）
MEMORY_ENABLED=True
MEMORY_AUTO_SAVE_HISTORY=True
```

### 3. 数据库迁移

```bash
python scripts/init_db.py
python scripts/migrate_add_memory_tables.py
python scripts/create_admin.py
python scripts/create_test_users.py    # 可选：创建测试账号
```

### 4. 启动服务

```bash
# 终端 1：启动后端（端口 8000，自动启动 Flue Agent 子进程）
python run_backend.py

# 终端 2：启动前端（端口 3000）
cd frontend && npm run dev
```

> `FLUE_AGENT_ENABLED=True` 时后端会自动启动 Flue Agent（端口 3002），无需单独启动。

### 5. 局域网访问

后端和前端均绑定 `0.0.0.0`，局域网内其他设备可通过 IP 访问：

```
前端: http://<服务器IP>:3000
后端: http://<服务器IP>:8000
```

> 需要在 `.env` 的 `CORS_ORIGINS` 中添加访问地址，并开放防火墙端口 3000、8000。

### 6. 登录

打开 `http://localhost:3000`，默认账号：

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| `admin` | `admin123` | 管理员 | 系统管理员 |
| `zhangwei` | `test1234` | 用户 | 张伟（运维主管） |
| `lina` | `test1234` | 用户 | 李娜（服务台） |
| `wangfang` | `test1234` | 用户 | 王芳（开发工程师） |
| `liuqiang` | `test1234` | 用户 | 刘强（安全审计） |

> 各账号数据通过 `user_id` 外键隔离：会话、消息、报表、偏好、分析历史互不可见。

## 项目结构

```
├── backend/                          # FastAPI 后端
│   ├── main.py                       # 应用入口 + 生命周期管理
│   ├── config.py                     # 环境配置 (Pydantic Settings)
│   ├── database.py                   # 数据库连接
│   ├── models.py                     # SQLAlchemy 数据模型（含记忆表）
│   ├── schemas.py                    # Pydantic 请求/响应模型
│   ├── auth.py                       # JWT 认证
│   ├── dependencies.py               # FastAPI 依赖注入
│   ├── utils.py                      # 工具函数
│   ├── routers/                      # API 路由
│   │   ├── chat.py                   # Agent 对话（含记忆 Hook）
│   │   ├── auth.py                   # 认证
│   │   ├── analytics.py              # 数据分析（支持多数据源）
│   │   ├── reports.py                # 报表管理
│   │   ├── datasources.py            # 数据源管理（预览+确认上传）
│   │   └── skills.py                 # Skill 管理
│   ├── services/                     # 业务服务
│   │   ├── ticket_processor.py       # 工单数据处理 + ProcessorManager
│   │   ├── memory_service.py         # 长记忆服务（4 种记忆）
│   │   ├── skill_engine.py           # Skill 执行
│   │   ├── intent_parser.py          # 意图解析（LLM + 规则 + 日期提取）
│   │   ├── datasource_detector.py    # 数据源切换检测
│   │   ├── chart_renderer.py         # ECharts option 生成
│   │   ├── export_service.py         # HTML/Excel 导出
│   │   ├── conversation_manager.py   # 对话上下文管理
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
│       │   ├── Chat.vue              # 对话主界面（含数据源切换器）
│       │   ├── Login.vue             # 登录页
│       │   ├── ReportList.vue        # 报表列表
│       │   ├── ReportDetail.vue      # 报表详情
│       │   ├── DataSourceManage.vue  # 数据源管理（两阶段上传）
│       │   └── SkillManage.vue       # Skill 管理
│       ├── components/               # 组件
│       │   ├── ChartRenderer.vue     # ECharts 渲染
│       │   ├── ChatMessage.vue       # 消息气泡
│       │   ├── ChatInput.vue         # 输入框
│       │   ├── KPICard.vue           # KPI 卡片
│       │   ├── LoadingIndicator.vue  # 加载指示器
│       │   └── DataSourceMappingPreview.vue  # 字段映射预览
│       ├── store/                    # Pinia 状态
│       │   ├── index.js              # auth / chat / analytics / report
│       │   └── datasource.js         # 多数据源状态
│       └── router/                   # 路由
│
├── flue-agent/                       # Flue Agent (Node.js)
│   ├── agent-server.js               # HTTP Agent Server（意图识别 + 日期提取）
│   ├── agents/                       # Markdown Agent 定义
│   │   └── intent-router.md          # 意图路由 Agent
│   └── package.json
│
├── internal/                         # Harness 调度层
│   ├── router/                       # 路由
│   │   ├── agent_registry.py         # Agent 注册中心
│   │   ├── skill_router.py           # Skill 调度
│   │   ── harness_router.py         # HTTP 端点
│   ├── tools/                        # MCP 工具
│   │   ├── base.py                   # 工具基类
│   │   ├── ticket_query.py           # 工单查询
│   │   ├── chart_render.py           # 图表渲染
│   │   └── report_export.py          # 报表导出
│   ├── context/                      # 上下文管理
│   │   ├── manager.py                # Token 感知窗口管理
│   │   └── compressor.py             # 对话压缩
│   ├── session/                      # 会话管理
│   │   ├── manager.py
│   │   └── models.py
│   ── memory/                       # 文件 KV 记忆存储
│       └── store.py
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
├── scripts/                          # 工具脚本
│   ├── init_db.py                    # 初始化数据库
│   ├── create_admin.py               # 创建管理员
│   ├── create_test_users.py          # 创建测试账号
│   └── migrate_add_memory_tables.py  # 长记忆表迁移
│
├── .env.example                      # 环境变量模板
├── run_backend.py                    # 后端启动脚本
└── data.xlsx                         # 示例工单数据
```

## 架构

```
┌─────────────┐     HTTP      ┌──────────────────┐     OpenAI API     ┌──────────────┐
│  前端        │ ───────────→ │  后端 FastAPI     │ ────────────────→ │  LLM API     │
│  Vue 3       │ ←──────────── │  (端口 8000)      │ ←──────────────── │  (DeepSeek等) │
│  (端口 3000)  │              │                    │                   │              │
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

## 数据库模型

### 核心表

| 表名 | 说明 | 关键外键 |
|------|------|----------|
| `users` | 用户账号 | — |
| `sessions` | 对话会话（含 context_summary） | `user_id` |
| `messages` | 对话消息 | `session_id`, `report_id` |
| `reports` | 分析报表 | `user_id`, `session_id`, `datasource_id` |
| `datasources` | 数据源（含 file_path） | — |
| `skills` | 分析技能 | `datasource_id` |

### 长记忆表

| 表名 | 说明 | 隔离字段 |
|------|------|----------|
| `user_preferences` | 用户偏好（常用维度、筛选条件） | `user_id` |
| `analysis_history` | 分析历史（结论、关键发现、标签） | `user_id`, `session_id`, `datasource_id` |
| `datasource_metadata` | 数据源元数据（字段结构、质量指标） | `datasource_id` |

## 数据隔离机制

系统通过 `user_id` 外键实现多用户数据隔离：

- **会话隔离**：每个用户只能查看自己的 `sessions` 和 `messages`
- **报表隔离**：每个用户只能查看自己的 `reports`
- **记忆隔离**：`user_preferences`、`analysis_history` 按 `user_id` 隔离
- **数据源共享**：`datasources` 全局共享，上传后所有用户可分析
- **JWT 认证**：所有 API 通过 `get_current_user` 中间件强制鉴权

## 支持的 LLM 提供商

| 提供商 | LLM_PROVIDER | LLM_BASE_URL | LLM_MODEL |
|--------|-------------|--------------|-----------|
| **DeepSeek** | `openai` | `https://api.deepseek.com` | `deepseek-chat` |
| **OpenAI** | `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| **Anthropic Claude** | `claude` | — | `claude-sonnet-4-6-20250514` |
| **本地模型 (vLLM/Ollama)** | `openai` | `http://localhost:8080/v1` | `qwen2.5-7b-instruct` |

## 日期筛选支持

用户在对话中使用自然语言即可过滤时间范围：

| 说法 | 自动转换 |
|------|----------|
| "五月份" / "5月" | `2026-05-01` ~ `2026-05-31` |
| "2026年3月" | `2026-03-01` ~ `2026-03-31` |
| "上个月" | 上月 1 日 ~ 上月最后一天 |
| "上周" | 上周一 ~ 上周日 |
| "本周" | 本周一 ~ 今天 |
| "最近一周" / "近7天" | 7 天前 ~ 今天 |
| "最近一个月" / "近30天" | 30 天前 ~ 今天 |
| "今年" | 今年 1 月 1 日 ~ 今天 |
| "去年" | 去年 1 月 1 日 ~ 去年 12 月 31 日 |

> 日期提取由 LLM 提示词 + 规则引擎双通道保障，Flue Agent 和后端 IntentParser 均支持。

## License

MIT
