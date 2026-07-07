# Metis 诊断服务（FastAPI）

> 单文件浏览器 UI + REST API。
> 用户输入自然语言 → 返回 v1 标签 + 真实 KB 条目 + 结构化动作。
> **LLM provider：仅 Dify（其他已退出 v1）。**

---

## 安装

```bash
cd /Users/pengfit/.openclaw/workspace/metis
python3 -m venv .venv        # 可选
source .venv/bin/activate
pip install -r app/requirements.txt

cp app/.env.example app/.env   # 编辑填 Dify API key
```

## 启动

```bash
# 方式 A: uvicorn 直接跑
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 方式 B: uvicorn --reload(改代码自动重载)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

打开：
- **本机**：`http://localhost:8000/`
- **同 WiFi**：`http://<你 Mac 的局域网 IP>:8000/`

## 端点

| 端点 | 方法 | 用途 |
|---|---|---|
| `/` | GET | 浏览器 UI（index.html） |
| `/health` | GET | 健康检查 |
| `/info` | GET | 服务信息 |
| `/diagnose` | POST | 核心诊断 |

完整 API 字段说明 → [docs/api.md](../docs/api.md)

## 配置

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `LLM_PROVIDER` | `dify` | （固定） |
| `LLM_MODEL` | `dify-app` | （固定） |
| `DIFY_API_BASE` | `https://api.dify.ai/v1` | Dify 端点根 URL |
| `DIFY_API_KEY` | — | Dify app 的 API key（必填后才有真 LLM） |
| `DIFY_APP_ID` | — | 可选, 人类可读 app 名 |
| `DIFY_USER` | `metis` | user id（让 Dify 跟踪对话） |
| `MOCK` | — | 设为 `1` 强制 mock（测试用, 忽略 DIFY_API_KEY） |

**配置示例（Dify）：**

```bash
export DIFY_API_BASE="https://api.dify.ai/v1"
export DIFY_API_KEY="app-***"
# 可选: export DIFY_APP_ID="诊断"
```

请求 body 也可临时指定：

```json
{
  "input": "...",
  "provider": "dify"
}
```

不配 DIFY_API_KEY（且没设 MOCK）→ 服务端走 mock fallback，notes 会标 `[MOCK 自动]`。

## Mock 模式

**没 API key 也能跑**。当以下任一成立：
- `MOCK=1` env 设置
- `DIFY_API_KEY` 没设

服务端会用预制响应（关键字匹配 7 个场景），返回字段的 `notes` 标 `[MOCK 自动]` 或 `[MOCK 强制]`。

适合：
- 浏览器 UI 体验
- 端到端测试（无需 Dify key）
- 离线演示

## 测试

跑端到端 smoke test：

```bash
cd /Users/pengfit/.openclaw/workspace/metis
python3 scripts/test_e2e.py        # 5 场景, mock LLM
python3 scripts/test_e2e.py S08   # 只跑 S08
```

输出示例：

```
[S03] input: 后天要面谈升职...
{
  "diagnoses": [...]
  ✓ 所有检查通过。 真实 LLM 跑通只需:
    export DIFY_API_KEY=***
```

## 项目结构

```
app/
├── main.py            ← FastAPI app, 4 端点
├── llm.py             ← LLM client (Dify only)
├── kb.py              ← KB 索引加载 + v1 tag / K-id 验证 + 复发追踪 + layer
├── __init__.py
├── static/
│   └── index.html     ← 单文件浏览器 UI (7.4 KB)
├── requirements.txt   ← 4 依赖
├── .env.example       ← 环境变量模板
└── README.md          ← 你在这里
```

## 浏览器 UI（单文件）

`app/static/index.html` 是个无依赖的 HTML+CSS+JS 单文件：
- 中文表单 + 诊断按钮
- 4 个预设情境（S01 拖延 / S03 焦虑-反刍 / S08 信念冲突 / S10 死亡焦虑）
- 随机示例切换
- 响应渲染：诊断卡片 + 首选动作高亮 + 完成判据
- 键盘快捷键：Cmd/Ctrl+Enter 提交
- viewport 配置好，移动端 OK

直接打开或 uvicorn 启动即可。

## 部署

### 本机（同上）
直接跑 uvicorn

### 公网
需要写 `Dockerfile` 和平台配置（Render / Fly.io / Railway 任一）。
TODO（与 [docs/development.md#部署](../docs/development.md#5-部署) 配对）

## 控制服务

```bash
# 查看 PID
cat /tmp/metis-server.pid

# 停服务
kill $(cat /tmp/metis-server.pid)

# 看实时日志
tail -f /tmp/metis-server.log
```

---

## 关联文档

- [docs/architecture.md](../docs/architecture.md) — 系统全景
- [docs/api.md](../docs/api.md) — HTTP API 参考
- [docs/prompt.md](../docs/prompt.md) — LLM prompt 设计
- [docs/layer-model.md](../docs/layer-model.md) — 5 层架构
- [docs/evaluation.md](../docs/evaluation.md) — 10 段测试场景
- [docs/development.md](../docs/development.md) — 改动流程

---

*整理于 2026-07-06*
