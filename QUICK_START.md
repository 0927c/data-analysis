# 快速启动指南

## 环境要求

| 工具 | 版本要求 |
|------|----------|
| **Node.js** | ≥ 18.0.0（Flue Agent + 前端需要） |
| **Python** | ≥ 3.10（后端需要） |
| **npm** | ≥ 9.0.0 |

---

## 1. 克隆 & 安装依赖

### 1.1 Python 后端依赖

```bash
cd <项目根目录>
pip install -r requirements.txt
```

### 1.2 Flue Agent 依赖

```bash
cd flue-agent
npm install
```

### 1.3 前端依赖

```bash
cd frontend
npm install
```

---

## 2. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env`，**最少需要配置以下项**：

```env
# LLM API 配置（必填）
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-你的API密钥

# 启用 Flue Agent（必填）
FLUE_AGENT_ENABLED=True

# 数据源（Excel 文件路径，非必填）
TICKET_EXCEL_PATH=./data.xlsx

# JWT 密钥（非必填，有默认值）
JWT_SECRET=改成随机字符串
```

### 可选的 LLM 提供商

| 提供商 | LLM_PROVIDER | LLM_BASE_URL | LLM_MODEL |
|--------|--------------|--------------|-----------|
| **DeepSeek** | `openai` | `https://api.deepseek.com` | `deepseek-chat` |
| **OpenAI** | `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| **Anthropic Claude** | `claude` | — | `claude-sonnet-4-6-20250514` |
| **本地模型 (vLLM/Ollama)** | `openai` | `http://localhost:8080/v1` | `qwen2.5-7b-instruct` |

---

## 3. 启动服务

按以下顺序依次启动三个服务：

### 3.1 启动 Flue Agent（端口 3002）

```bash
cd flue-agent
node agent-server.js
```

预期输出：

```
  ✓ Flue Agent 已启动
  • 端点: http://localhost:3002
  • 模型: deepseek-chat
  • Agent: intent-router
  • Skills: 2 个
```

> **保持此终端窗口打开**，Flue Agent 是常驻服务。

### 3.2 启动后端（端口 8000）

**新开一个终端**：

```bash
python run_backend.py
```

预期输出：

```
  ✓ LLM Provider 已初始化: openai / deepseek-chat
  ✓ Flue Agent 子进程已启动 (PID: 12345)
  INFO:     Uvicorn running on http://0.0.0.0:8000
```

> 注意：后端会自动启动一个 Flue Agent 子进程（如果 `.env` 中 `FLUE_AGENT_ENABLED=True`）。

### 3.3 启动前端（端口 5173）

**再新开一个终端**：

```bash
cd frontend
npm run dev
```

预期输出：

```
  VITE v5.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

---

## 4. 验证服务

### 4.1 检查后端健康状态

```bash
curl http://localhost:8000/api/health
```

返回：`{"status":"ok"}`

### 4.2 检查 Flue Agent 健康状态

```bash
curl http://localhost:3002/health
```

返回：`{"status":"ok","model":"deepseek-chat","agent":"intent-router"}`

### 4.3 测试意图识别

```bash
curl -X POST http://localhost:3002/agent/intent -H "Content-Type: application/json" -d "{\"message\":\"查询各状态工单数量\"}"
```

正常返回示例：

```json
{
  "skill_id": "ticket_analysis",
  "group_by": "status",
  "chart_type": "pie",
  "reasoning": "用户希望查询工单的状态分布情况"
}
```

### 4.4 打开浏览器

访问 **http://localhost:5173**，使用默认账号登录：

| 用户名 | 密码 |
|--------|------|
| `admin` | `admin123` |

---

## 5. 使用流程

1. **登录系统** → 进入主界面
2. **上传数据**（可选） → 进入"数据源管理"上传 ITSM Excel 文件
3. **开始对话** → 在聊天界面输入自然语言问题，如：
   - "各状态工单有多少？"
   - "哪些系统故障最多？"
   - "本月工单趋势如何？"
   - "运维质量分析一下"
4. **查看报表** → 对话中生成的图表可以保存为报表

---

## 6. 常见问题

### 端口被占用

如果端口被占用，启动前先清理：

```powershell
# 杀掉占用端口的进程
netstat -ano | findstr :3002    # 查看 PID
taskkill /PID <PID> /F

netstat -ano | findstr :8000
taskkill /PID <PID> /F

netstat -ano | findstr :5173
taskkill /PID <PID> /F
```

### Flue Agent 启动失败

```bash
cd flue-agent
# 检查依赖是否完整
npm ls

# 重新安装
rm -rf node_modules package-lock.json
npm install
```

### 后端提示 LLM Provider 初始化失败

检查 `.env` 中的 `LLM_API_KEY` 是否正确配置，以及网络是否能访问 API 地址。

### 前端页面空白

确认后端是否正常运行，并检查浏览器控制台是否有跨域报错。CORS 配置在 `.env` 的 `CORS_ORIGINS` 中。

---

## 7. 架构概览

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

- **前端** → **后端**: 用户对话请求发送到 FastAPI
- **后端** → **Flue Agent**: 后端的 `FlueProvider` 通过 HTTP 调用 Flue Agent 进行意图识别
- **Flue Agent** → **LLM API**: Flue Agent 调用 OpenAI 兼容 API 完成 LLM 推理

---

## 8. 一键启动（Windows）

在项目根目录下创建 `start-all.bat`：

```batch
@echo off
cd /d "%~dp0"

echo ==============================
echo   启动 Flue Agent (端口 3002)
echo ==============================
start "Flue Agent" cmd /c "cd /d flue-agent && node agent-server.js"
timeout /t 3 /nobreak >nul

echo ==============================
echo   启动后端 (端口 8000)
echo ==============================
start "Backend" cmd /c "python run_backend.py"
timeout /t 5 /nobreak >nul

echo ==============================
echo   启动前端 (端口 5173)
echo ==============================
start "Frontend" cmd /c "cd /d frontend && npm run dev"

echo.
echo 所有服务已启动！
echo Flue Agent: http://localhost:3002
echo 后端:       http://localhost:8000
echo 前端:       http://localhost:5173
echo.
pause
```
