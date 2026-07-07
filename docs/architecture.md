# 架构

## 1. 系统全景 (v1.2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                            浏览器 (localhost:8000)                     │
│                                                                         │
│   输入: textarea                                                       │
│   输出: tags + 一键动作 + 时段 banner                                │
└──────────────────────┬──────────────────────────────────────────────┘
                       │  POST /diagnose  {input: ...}
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FastAPI  (app/main.py)                          │
│                                                                         │
│   ┌──────────────┐    ┌──────────────────────┐    ┌──────────────┐   │
│   │ POST handler │───▶│ KB hybrid search     │───▶│ LLM client   │   │
│   │              │    │  (kb.py)             │    │  (llm.py)    │   │
│   │              │    │   • keyword 检索     │    │   • 拼 KB    │   │
│   │              │    │   • bge-m3 cosine   │    │     context   │   │
│   │              │    │   • 融合 top-25      │    │   • 调用     │   │
│   │              │    └──────────┬───────────┘    │     Dify     │   │
│   │              │               │ kb_context     │   • mock     │   │
│   │              │               ▼                └──────┬───────┘   │
│   │              │    ┌──────────────────────┐        │           │
│   │              │◀───│ validate + enrich    │◀───────┘           │
│   │              │    │   - 过滤 v1 外的 tag  │                    │
│   │              │    │   - 过滤不存在的 K   │                    │
│   │              │    │   - 拉 actions (top6) │                    │
│   │              │    │   - time filter      │                    │
│   │              │    │   - record_tags      │                    │
│   │              │    └──────────────────────┘                    │
│   └──────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────┘
                       │
                       ▼ 读
┌─────────────────────────────────────────────────────────────────────┐
│              Knowledge Base (Knowledge Base/0?-*.json)               │
│         + embedding_index (kb.py 内存, bge-m3 1024-dim)              │
└─────────────────────────────────────────────────────────────────────┘
                       │
                       ▼ 调 (HTTP, 首次冷启动 ~18s 一次性)
┌─────────────────────────────────────────────────────────────────────┐
│         本地 ollama + bge-m3  (OLLAMA_URL=http://localhost:11434)   │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. 数据流（端到端 · v1.2）

```
Step 1 · HTML 用户点击"诊断"
   │
   ▼
Step 2 · fetch('/diagnose', {input: "..."})
   │
   ▼
Step 3 · main.py 收到请求
   │   • Pydantic 验证 input 必填
   │
   ▼
Step 3.5  ★ v1.2 新增 ── KB 检索 (kb.search_hybrid)
   │   • keyword 检索 (name strict + summary 召回 + stopwords)
   │   • bge-m3 cosine 检索 (KB embedding index, 1024-dim)
   │   • 融合排序 top-25 → kb_hits
   │   • 拼 kb_context = <<KB_CONTEXT>> block 供 LLM
   │   • ollama 不可用 → 自动降级纯关键词
   │
   ▼
Step 4 · llm.call_llm(input, kb_context=kb_context)
   │   • 拼 query + kb_context (Dify chat 模式)
   │   • 或拼 inputs[USER_DESCRIPTION] (Dify workflow 模式)
   │   • 检查 MOCK / API key
   │     ├─ MOCK=1 → 关键字匹配 → canned JSON (kb_context 被忽略)
   │     ├─ 有 key → httpx 调 Dify API
   │     └─ 无 key → silent fallback to mock
   │   • 解析 JSON → 返回 raw dict
   │
   ▼
Step 5 · _validate(raw_dict)
   │   • 过滤 v1 之外的 tag (幻觉预防)
   │   • 过滤 KB 不存在的 K-id (幻觉预防)
   │   • 钳制 confidence 到 [0, 1]
   │   • 对每条 diagnosis 调用 top_actions_for(k_ids, max_n=6)  ★ v1.2 max_n=6
   │     ├─ 跨所有 k_ids 收集 actions
   │     ├─ when_rank (now < today < this_week) 排序
   │     ├─ 同 when 按 min 升序
   │     └─ label 去重, 截断到 6 个
   │
   ▼
Step 5.5  ★ v1.2 新增 ── time_sensitive_filter
   │   • 当前 hour 判定 (深夜 22-6)
   │   • 过滤掉"剧烈运动""联系朋友""出门散步"等耗能/社交类
   │
   ▼
Step 5.7  ★ v1.2 新增 ── record_tags + next_layer
   │   • 记录本次诊断的 tags (供下次复发信号判定)
   │   • 如触发 (同 tag 7d ≥ 3次) → 返回 principle/theme 层
   │
   ▼
Step 6 · 返回 JSON (含 kb_hits + time_context)
   │
   ▼
Step 7 · UI 渲染
   │   • 顶部时段 banner (time_context)
   │   • 诊断卡片 (tag + evidence + actions 三档分组)
   │   • next_layer 卡 (如触发)
```

## 3. 模块依赖 (v1.2)

```
KB-JSON ←── build_kb_index.py ──→ kb-index.json ─── build_prompt.py ──→ prompt-v1.md
                                                                              │
                                                                              ▼
                                                                          app/llm.py 加载
                                                                              │
                                                                              ▼
                                              ┌────────────────┐    ┌────────┴────────┐
                                              │ app/kb.py 读   │    │ app/main.py     │
                                              │  kb-index.json │◀───│ 端到端路由       │
                                              │  + embedding   │    │ /diagnose       │
                                              │    index       │    │ /admin/reset    │
                                              └────────┬───────┘    └────────┬────────┘
                                                       │                     │
                                                       ▼                     ▼
                                                 ollama bge-m3         Dify API
                                                (HTTP /api/            (chat-messages /
                                                 embeddings)            workflows/run)
```

## 4. 关键不变量（每次改动都要保持的）

| 不变量 | 怎么保证 |
|---|---|
| v1 标签只有 25 个 | [docs/taxonomy.md](taxonomy.md) 是 ground truth,LLM 输出受 prompt 约束,_validate 后端过滤 |
| K-id 真实存在 | [scripts/audit_kb.py](../scripts/audit_kb.py) 在每次改动后跑 |
| 动作是动作动词（不是概念名） | [docs/action-schema.md](action-schema.md) 锁版,prompt 强制 matches, server 从 KB 读 |
| 服务端不信任 LLM 写 actions | app/_validate 不解析 actions 字段,只读 KB |
| actions[0] 是 now/min 最小 | top_actions_for 排序逻辑 |
| **kb_hits 反映 KB 检索真实命中的 top-K** ★ v1.2 | `kb.search_hybrid()` 返回值直接透传,不二次过滤 |
| **time_context 由服务端时间判定** ★ v1.2 | `datetime.now().hour` 经 `time_context()` 映射,客户端不可伪造 |
| **time_sensitive_filter 不删除 now 类** ★ v1.2 | 只过滤"耗能/社交"关键词匹配的,now 类中的轻量动作保留 |

## 5. 不可恢复决定（一旦锁定，不轻易改）

- **25 个 v1 标签**：扩展但不动 id/name。下调标签要非常谨慎（要看 KB 实际覆盖）
- **Action 5 字段**：action_id 不要加，JSON 字段不要扩张
- **Top-3 截断**：v1.2 调整为 top-6 给 time filter 留余量, 但 max_n=6 是调优常量可改
- **time_filter 关键词白名单**：`_NIGHT_BLOCKED` 是 MVP 启发式,完整方案是 KB 加 `time_horizon` 字段 (留待)

## 6. 失败模式（哪些坏了会怎样）

| 失败 | 检测 | 兜底 |
|---|---|---|
| LLM 发明新标签 | prompt 约束 + _validate 过滤 | 丢弃该诊断 |
| LLM 编 K-id | _validate 查询 KB | 丢弃该 K-id |
| LLM JSON 解析失败 | llm.py 抓 `{...}` 子串 | 抛 500 + 错误信息 |
| LLM 调用超时 | httpx timeout | 抛 500 |
| API key 没设 | `os.environ.get("DIFY_API_KEY")` 检查 | 静默 mock fallback, notes 标 `[MOCK 自动]` |
| KB 损坏 | audit_kb 启动前跑 | 阻止启动 + 报错 |
| **ollama 不可用** ★ v1.2 | `_embedding_index()` 启动时 try/except | 降级到纯关键词检索, `embed_ready=false`, `kb_hits` 仍返回但 score 仅基于关键词 |
| **bge-m3 模型未拉取** ★ v1.2 | ollama 调用 `404 model not found` | 同 ollama 不可用,降级 + warning |
| **Dify workflow 输入变量名错配** ★ v1.2 | `400 invalid_param` from Dify | 抛 500 + 详细错误,提示检查 `DIFY_INPUT_VAR` |
| **Dify app 类型探测失败** ★ v1.2 | chat-messages + workflows/run 都 4xx | 抛 500 + 详细错误,清 `dify_mode_cache` 后重试 |

---

## 7. 部署

### 前置依赖
- Python 3.10+
- ollama 本地运行 + bge-m3 模型已拉取 (`ollama pull bge-m3`)
- Dify app 已配置 (chat 或 workflow)

### 本机
```bash
cd /Users/pengfit/.openclaw/workspace/metis
pip install -r app/requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 首次 /diagnose 触发 embedding 索引构建 (~18s, 一次性)
```

### 同 WiFi 跨设备
Mac 防火墙放行 + `http://<Mac-IP>:8000/`

### 公网部署（待写）
Render / Fly.io / Railway 任选。Dockerfile 需要写。**注意**：embedding 索引构建是冷启动的一次性开销 18s，公网部署需要预热。

---

*整理于 2026-07-06 · v1.2 更新于 2026-07-07*
