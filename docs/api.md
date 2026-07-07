# HTTP API

> FastAPI 服务在 [app/](../app/README.md)，对外暴露 4 个端点。  
> **唯一 LLM provider = Dify** (OpenClaw / OpenAI / Anthropic 已退出 v1)。

## 端点总览

| 端点 | 方法 | 用途 | 响应格式 |
|---|---|---|---|
| `/` | GET | 浏览器 UI | HTML (text/html) |
| `/health` | GET | 健康检查（含 embedding 状态） | JSON |
| `/info` | GET | 服务信息（含 embed backend） | JSON |
| `/diagnose` | POST | 核心诊断接口 | JSON |
| `/admin/reset` | POST | 清运行时缓存 | JSON |

---

## 1. `GET /`

浏览器 UI。直接打开 `http://localhost:8000/`。

返回 [app/static/index.html](../app/static/index.html)：单页 HTML，文本框 + 一键诊断按钮 + 4 个预设场景。

不需要任何配置，浏览器 → 服务端 → 渲染响应全 HTML。

---

## 2. `GET /health`

```bash
curl http://localhost:8000/health
```

**响应 200**：

```json
{
  "status":           "ok",
  "service":          "metis-diagnose",
  "v1_tags_loaded":   25,
  "embed_ready":      true,
  "embed_model":      "bge-m3"
}
```

- `embed_ready`: 本地 ollama + bge-m3 是否可用（影响 KB 检索精度）
- `embed_model`: 使用的 embedding 模型名，ollama 不可用时为 `null`

用于容器健康检查、负载均衡器探活。`embed_ready=false` 不阻塞服务（自动降级到纯关键词检索），但意味着 KB 检索精度下降。

---

## 3. `GET /info`

```bash
curl http://localhost:8000/info
```

**响应 200**：

```json
{
  "service":            "metis-diagnose",
  "version":            "1.2",
  "endpoints":          ["/", "/health", "/diagnose", "/info", "/admin/reset"],
  "ui":                 "/  (browser frontend)",
  "v1_taxonomy_size":   25,
  "embed_backend":      "ollama:bge-m3"
}
```

- `embed_backend`: 实际使用的 embedding 后端；不可用时为 `"fallback:keyword-only"`
- 端点列表含 `/admin/reset`

---

## 4. `POST /diagnose`（核心）

```bash
curl -X POST http://localhost:8000/diagnose \
  -H 'Content-Type: application/json' \
  -d '{"input": "最近一个重要提案拖了两周写不出第一段"}'
```

### 请求体

```json
{
  "input":    "<string, 1-4000 字符 · 必填>",
  "provider": "<string, 可选 · 'dify'>",
  "model":    "<string, 可选 · 覆盖默认模型>"
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `input` | string | ✓ | — | 用户的自然语言描述，1-4000 字符 |
| `provider` | string | ✗ | `LLM_PROVIDER` env / `dify` | 现在只有 `dify` |
| `model` | string | ✗ | `LLM_MODEL` env / `dify-app` | 模型名 |

如请求 body 不指定 provider/model，从环境变量 `LLM_PROVIDER` / `LLM_MODEL` 读；都未设则用默认值：
- **dify** → `dify-app` (Dify 用 app 自配置)

请求 body 传 `provider` 现在只接受 `"dify"`。

### 响应 200 — 完整 Schema

```json
{
  "diagnoses": [
    {
      "tag":         "拖延",
      "confidence":   0.92,
      "evidence":     "拖了两周写不出第一段",
      "k_ids":        ["K035", "K036"],
      "actions": [
        {
          "label": "5秒起跑",
          "do":    "倒数5秒立刻打开文档输入第一句(不限好坏)",
          "when":  "now",
          "min":   1,
          "mark":  "你输出了第一句(烂也算赢)"
        },
        {
          "label": "拆启动动作",
          "do":    "把'起草段'改成'打开文档',单一按钮式启动",
          "when":  "now",
          "min":   2,
          "mark":  "打开了文档"
        },
        {
          "label": "画圆练习",
          "do":    "一笔画完圆,不对齐,看'完成'",
          "when":  "today",
          "min":   1,
          "mark":  "圆画了"
        }
      ]
    }
  ],
  "notes":        "[MOCK 自动] 未检测到 DIFY_API_KEY, 使用预制响应",
  "fallback":     "",
  "kb_hits":      [
    {"kid": "K036", "score": 0.8721},
    {"kid": "K035", "score": 0.7240},
    {"kid": "K018", "score": 0.5011}
  ],
  "time_context": {
    "mode":  "morning",
    "label": "早晨模式",
    "icon":  "🌅",
    "hour":  7
  },
  "next_layer": {
    "triggered":  false,
    "hot_tag":    null,
    "count":      1,
    "window":     "7d"
  }
}
```

**v1.2 新增字段**：
- `kb_hits` (array): 服务端 KB 检索命中的 top-K K-id + 融合分数（关键词 × embedding cosine），前端可展示"哪些 KB 条目参与了这次诊断"
- `time_context` (object): 服务端判断的当下时段，UI 据此展示时段 banner + 过滤不合时宜的 actions

### 响应字段细则

#### 顶层

| 字段 | 类型 | 含义 |
|---|---|---|
| `diagnoses` | array | 1-3 个诊断，**空数组合法** |
| `notes` | string | LLM 给出的一句话整体说明 / 覆盖情况 / mock 标记 |
| `fallback` | string | 当 `diagnoses` 为空时，用户的可选方向 |
| `kb_hits` | array | KB 检索命中的 top-K (kid, score)，供前端透明度展示 |
| `time_context` | object | 当下时段信息 (mode/label/icon/hour)，UI 据此渲染 |
| `next_layer` | object | 复发信号触发时浮现 principle/theme 层 |

#### `kb_hits[i]` (v1.2 新增)

| 字段 | 类型 | 含义 |
|---|---|---|
| `kid` | string | KB 条目 ID (e.g. "K035") |
| `score` | float | hybrid 检索融合分数 (0-1)，含关键词 + embedding cosine |

检索顺序：`kb.search_hybrid()` → 关键词 × bge-m3 cosine 融合 → top-K（默认 25）
ollama 不可用时降级到纯关键词检索。

#### `time_context` (v1.2 新增)

| 字段 | 类型 | 含义 |
|---|---|---|
| `mode` | string | 6 档之一: `morning` / `forenoon` / `noon` / `afternoon` / `evening` / `night` |
| `label` | string | 中文标签 (e.g. "早晨模式") |
| `icon` | string | emoji (e.g. "🌅") |
| `hour` | int | 0-23 当前小时 |

时段对照：
- `morning`: 6-9 (🌅 早晨模式)
- `forenoon`: 9-12 (☀️ 上午)
- `noon`: 12-14 (🍚 午间)
- `afternoon`: 14-18 (☕ 下午)
- `evening`: 18-22 (🌆 傍晚)
- `night`: 22-6 (🌙 深夜模式)

#### `diagnoses[i]`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `tag` | string | ✓ | 25 个 v1 标签之一（幻觉外的会被服务端丢弃） |
| `confidence` | float | ✓ | 0.0-1.0，钳制后保留 2 位小数 |
| `evidence` | string | ✓ | 用户原话中的具体短语 |
| `k_ids` | array | ✓ | 1-4 个真实存在的 K-id（不存在的会被服务端丢弃） |
| `actions` | array | ✓ | **从 KB 拉的真实结构化动作对象**，top 3，跨 K-id 去重 |

#### `actions[i]`

| 字段 | 类型 | 含义 |
|---|---|---|
| `label` | string | 动作标题 |
| `do` | string | 具体步骤 |
| `when` | string | `now` / `today` / `this_week` |
| `min` | int | 预估分钟 |
| `mark` | string | 完成判定 |

#### `next_layer` (仅在 ≥3 次/7d 复发时触发)

详见 [docs/layer-model.md](layer-model.md) §5-7。

### 响应 400 / 500 / 503

| 状态 | 含义 |
|---|---|
| 400 | 请求体格式错误（如 input 为空） |
| 500 | LLM 调用失败 / API key 缺失 / 解析失败 / Dify 调用失败 |
| 503 | （预留）服务过载时 |

错误响应是 plain text（不是 JSON），例如：

```
500 Internal Server Error
DIFY_API_KEY 未设置. 请在 app/.env 或环境变量中配置 Dify app key.
或在请求 body 里指定 provider='mock'(或设 MOCK=1) 走预制响应.
```

## 5. 排序规则 — `actions[0]` 就是"今天救命"

服务端 `_validate` 之后的 `top_actions_for()` 函数（v1.2 调整）：

```
输入: 一组 K-id (来自 diagnoses[i].k_ids[:4])
输出: 排序后的 actions 列表, 流程:
    1. top_actions_for(k_ids, max_n=6) 拉 6 个候选 (留余量给时间过滤)
    2. 排序:
       a. when_rank: now=0, today=1, this_week=2
       b. 同 when 按 min 升序 (1m 优先于 10m)
       c. label 去重 (同名动作只保留第一条)
    3. time_sensitive_filter(actions, hour) — 深夜剔除耗能/社交类
```

**含义**：`actions[0]` 是用户"立刻 1 分钟内能做的救命稻草"。

**v1.2 改动**：
- `max_n` 从 3 调到 6（给 time_sensitive_filter 留余量）
- 深夜 (22-6) 自动过滤"剧烈运动""联系朋友""出门散步"等不合时宜的 actions

---

## 5.1 `POST /admin/reset` (v1.2 新增)

清运行时缓存：

```bash
curl -X POST http://localhost:8000/admin/reset
```

**响应 200**：

```json
{
  "status":  "reset",
  "cleared": ["embedding_index", "dify_mode_cache", "recurrence_tracker"],
  "note":    "下次 /diagnose 会重建 embedding index (首调用 ~18s)"
}
```

清掉：
- `embedding_index` (lru_cache) — 下次 `/diagnose` 首次调用触发重建 ~18s
- `dify_mode_cache` — Dify app 探测模式 (chat vs workflow) 重置
- `recurrence_tracker` — next_layer 复发计数清零

**用途**：
- 改了 KB 后想强制清缓存
- Dify app 类型从 chat 改到 workflow 后重置探测
- 调试 / 重置状态

---

## 6. CORS

允许所有来源 `allow_origins=["*"]`。任何前端都能调。

生产时建议改白名单。

## 7. Rate Limiting

未实现。如需要可在 FastAPI 中间件加 `slowapi` 或 nginx 层做。

## 8. Auth

未实现。本机用 OK。公网部署前必须加。

---

## 9. Dify 配置示例

```bash
export LLM_PROVIDER=dify
export DIFY_API_BASE=https://api.dify.ai/v1
export DIFY_API_KEY=app-xxx                  # 必填
export DIFY_INPUT_VAR=USER_INPUT             # v1.2: Dify workflow app 的输入变量名 (默认 USER_DESCRIPTION, 实际可能是 USER_INPUT)

# 可选:
export DIFY_APP_ID="诊断"                   # 人类可读名称, 不参与 HTTP
export DIFY_USER=metis                       # user id
```

**`DIFY_INPUT_VAR` 是 v1.2 新增** — 用于 Dify workflow app（不是 chat app）。Dify workflow 的输入变量名取决于 app 的设置，可能是 `USER_DESCRIPTION` / `USER_INPUT` / `query` 等任意名。**先在 Dify Studio 看自己 app 的输入变量名**，再设到 `.env`。错配会导致 `400 invalid_param` 错误。

**在 Dify Studio 里配置 app 的 prompt:**
1. 创建 app (Chat App 或 Workflow App, blocking 模式)
2. **system prompt 里贴** v1.2 的诊断指令 (25 个 v1 标签 + 7 条硬约束 + KB 检索结果引用规范)
3. app 输出 `answer` 字段必须是诊断 schema JSON
4. 拿 app 的 API key

**Dify app 的 `answer` 字段预期返回：**

```jsonc
{
  "diagnoses": [{"tag": "...", "confidence": ..., "evidence": "...", "k_ids": ["..."]}],
  "notes": "...",
  "fallback": ""
}
```

如果 Dify app 输出不是这个 schema，server 走默认 fallback 后 `diagnoses: []` 并 `notes` 输出错误。

### v1.2 prompt 关键约束 (Dify Studio 里要写)

```
7 条硬约束：
1. tag 只能从 KB_CONTEXT 里的「tag 候选」中选
2. diagnoses ≤ 3, 按 confidence 降序
3. evidence 必须引用 USER_INPUT 或 KB_CONTEXT 里的具体短语 (≤30字), 不要泛说
4. k_ids 必须真实存在于 KB_CONTEXT 候选里 (服务端二次校验)
5. 不输出 interventions / actions 字段 (服务端从 KB 拉)
6. 不给建议、不开药方
7. 宁少勿真: 不确定时 diagnoses = [], 必须填 fallback
```

**核心**: 第 3 条「evidence 引 KB 短语」是 C 方案全部意义所在，必须写清楚。

## 10. Mock 模式

**没 DIFY_API_KEY 也能跑**。当以下任一成立：
- `MOCK=1` env 设置
- `DIFY_API_KEY` 没设

服务端会用预制响应（关键字匹配 7 个场景），返回字段的 `notes` 标 `[MOCK 自动]` 或 `[MOCK 强制]`。

适合：
- 浏览器 UI 体验
- 端到端测试
- 离线演示

---

## 11. v1.2 增量小结

- 新增 `kb_hits` (KB 检索透明度) + `time_context` (时段信息) 字段
- 新增 `/admin/reset` 端点
- `/health` 加 `embed_ready` / `embed_model` 字段
- `/info` 加 `embed_backend` 字段
- `actions` 排序 `max_n` 3 → 6，加 `time_sensitive_filter`
- Dify workflow 必须配 `DIFY_INPUT_VAR`

---

*整理于 2026-07-06 · v1.2 增量更新于 2026-07-07*
