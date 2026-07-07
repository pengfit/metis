# Metis 诊断引擎 · 项目入口

> **症状诊断 + 可执行动作**：从用户自然语言描述出发，给出 v1 标签 + 知识库条目 + 立刻能做的具体动作。

---

## 它做什么

用户输入一句话：_"最近一个重要提案拖了两周写不出第一段"_

系统返回：

```json
{
  "diagnoses": [
    {
      "tag": "拖延",
      "confidence": 0.92,
      "evidence": "拖了两周/写不出第一段",
      "k_ids": ["K035", "K036"],
      "actions": [
        {
          "label": "5秒起跑",
          "do": "倒数5秒立刻打开文档输入第一句(不限好坏)",
          "when": "now",
          "min": 1,
          "mark": "你输出了第一句(烂也算赢)"
        }
      ]
    }
  ]
}
```

`actions[0]` = **今天的救命动作**，1 分钟内可做。

---

## 5 分钟跑起来

```bash
cd /Users/pengfit/.openclaw/workspace/metis
pip install -r app/requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 浏览器 → http://localhost:8000/
```

**不带 API key 也能玩**：服务端自动 fallback 到 mock 响应，notes 字段标 `[MOCK]`。
要真实 LLM：`echo "OPENAI_API_KEY=***" >> app/.env` 后重启。

---

## 项目结构

```
metis/
├── README.md                  ← 你在这里
├── docs/                      ← 全部权威文档
├── Knowledge Base/            ← 111 条数据 + 原始题录 + 机器生成物
│   ├── 01-身份.json … 08-意义与目的.json
│   ├── 米提斯.md              ← 原始 110 题录
│   ├── INDEX.md               ← KB 导航
│   └── _eval/                 ← 机器生成(prompt, 索引, 测试数据)
├── scripts/                   ← Python 工具脚本
│   ├── relabel_kb.py          ← 111 条 KB 重打 v1 标签
│   ├── refactor_actions.py    ← 概念名 → 动作动词
│   ├── audit_kb.py            ← 健康检查
│   ├── build_kb_index.py      ← 生成检索索引
│   ├── build_prompt.py        ← 重建诊断 prompt
│   ├── test_e2e.py            ← 端到端 smoke 测试
│   └── _archive_graph_v1/     ← v0 失败的图谱实验(归档)
└── app/                       ← FastAPI 服务 + 浏览器 UI
    ├── main.py / llm.py / kb.py
    ├── static/index.html      ← 单文件 UI
    └── requirements.txt / .env.example
```

---

## 数据流（一句话）

```
KB JSON  →  build_kb_index.py  →  kb-index.json  →  build_prompt.py  →  prompt-v1.md
                                                                  ↓
                 HTTP /diagnose  ←  call_llm()  ←  FastAPI 启动时加载
                                       ↓
                             LLM 选 tag + K-id
                                       ↓
                 服务端 _validate + top_actions_for
                                       ↓
                        结构化 actions JSON
                                       ↓
                            浏览器 UI 渲染
```

每条管道的输入/输出/契约详见 [`docs/architecture.md`](docs/architecture.md)。

---

## 关键设计决策

| 决策 | 原因 |
|---|---|
| **症状驱动标签**（不是概念） | 用户描述自己用口语，不用术语 |
| **25 个 v1 标签** | 比 100+ 易记；比 5 个覆盖广 |
| **LLM 只选 tag + K-id**，不写 actions | 防幻觉；server 从 KB 拉真实动作 |
| **每诊断 3 个动作** | 既不冗余也不贪 |
| **`now` > `today` > `this_week`** 排序 | 用户最关心"立刻能做的" |
| **mock fallback** | UI 立刻可玩，不需要立刻配 key |
| **CORS 全开** | 任何前端都能调 |

---

## 文档

**权威文档全部在 [`docs/`](docs/README.md)**。  

| 速查 | 看哪份 |
|---|---|
| 我想知道项目做什么 | 你已经在这里 ✓ |
| 我想改 KB 数据 | [docs/development.md](docs/development.md#改-KB) |
| 我想调 prompt | [docs/prompt.md](docs/prompt.md) |
| 我想加 1 个 v1 标签 | [docs/taxonomy.md](docs/taxonomy.md#扩展) |
| 我想跑端到端 | [docs/api.md](docs/api.md) + [docs/development.md](docs/development.md#端到端) |
| 我想写测试场景 | [docs/evaluation.md](docs/evaluation.md) |

---

## 更新日志

### v1.2 · 2026-07-07 · 让 KB 进“理解”那一刀

**主题：让 KB 从“事后兜底”变成“事前检索”，让“今日行动”对当下敏感。**

#### C 方案 — KB 先检索 · LLM 在候选里判断
- `app/kb.py` 新增：
  - `_tokenize()` / `_STOPWORDS` — 中文友好分词 + 停用词过滤
  - `search(query, top_k)` — 关键词检索（name 严格 substring + summary 召回 + IDF-free 评分）
  - `search_hybrid(query, top_k, alpha=0.5)` — 关键词 × ollama bge-m3 embedding cosine 融合排序
  - `embed_query()` / `_ollama_embed()` — 调本地 ollama `/api/embeddings`（1024 维）
  - `_embedding_index()` — 启动时一次性 embed KB 全部 111 条，~18s，冷启动一次性成本
- `app/llm.py` 调整：
  - `call_llm()` 接 `kb_context` keyword-only 参数
  - chat-messages 模式：KB context 拼到 query，同时塞 `inputs.kb_context` 供 prompt 模板引用
  - workflow 模式：拼到 USER_DESCRIPTION，同时塞 `inputs.KB_CONTEXT` 变量
- `app/main.py` `/diagnose` 端点：
  - 调用顺序：先 `kb.search_hybrid()` → `kb.context_for_from_hits()` → `llm.call_llm(kb_context=…)`
  - 响应加 `kb_hits` 字段（顶面透明度，前端可展示）
- `docs/prompt.md` 重写第 5 节：KB 上下文 = 外部检索 + 内嵌并存
- 验收：4 场景 (S01/S03/S08/S10) tag 全部命中，evidence 逐字引用户原话

#### D 方案 — “今日行动”对当下敏感
- `app/kb.py` 新增：
  - `time_context(hour)` — 6 档时段判断（morning / forenoon / noon / afternoon / evening / night）
  - `time_sensitive_filter(actions, hour)` — 深夜过滤耗能/社交类 action（“剧烈运动”“联系朋友”“出门散步” 等）
  - `_NIGHT_BLOCKED` — 深夜黑名单关键词集合
- `app/main.py`：
  - `_validate` 里 `max_n=3` → `max_n=6`（给 filter 留余量）
  - 响应加 `time_context` 字段，UI 可以用来展示时段提示
- `app/static/index.html`：
  - actions 按 `when` 分三档渲染（⏰ 现在做 / 📅 今天做 / 📆 这周做）
  - 顶部加时段 banner（6 种 mode + 时段提示语）
  - 分组标题色 + 数量徽标 + 首个 “首选” 高亮
- 验收：hour=23 过滤 5→2 actions；UI 截图显示早晨模式 + 三档分组

#### 修复 / 调整
- `app/.env` 加 `DIFY_INPUT_VAR=USER_INPUT`（Dify workflow 输入变量名不是默认的 `USER_DESCRIPTION`）
- `app/main.py` `/admin/reset` 端点 — 清运行时缓存（embedding index / mode cache / recurrence）
- `app/main.py` `/health` 加 `embed_ready` / `embed_model` 字段
- `app/main.py` `/info` 加 `embed_backend` 字段

#### 环境依赖
- 本地 **ollama** + **bge-m3** 模型（1024 维，CPU 跑 ~50ms/条）。没有 ollama 自动降级到纯关键词检索

#### 不变更项
- v1 标签（仍 25 个）
- KB 本身（仍是 111 条）
- Prompt 业务逻辑（4 + 5 + 6 三套）


---

*整理于 2026-07-06 · 米提斯（Metis）*
*v1.2 更新于 2026-07-07 · C 方案 + D 方案*
