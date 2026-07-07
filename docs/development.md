# 开发流程

> 改动任何一部分（KB / Prompt / Action / 服务端 / LLM）的完整步骤。

## 0. 第一次跑通

### 前置依赖 (v1.2)
- Python 3.10+
- **ollama** 本地运行 + **bge-m3** 模型 (1024 维 embedding)
  ```bash
  brew install ollama  # 或官网安装
  ollama serve &        # 启动服务 (默认 localhost:11434)
  ollama pull bge-m3    # 拉取 embedding 模型
  ```
- (可选) Dify app 已配置 + DIFY_API_KEY

### 启动

```bash
cd /Users/pengfit/.openclaw/workspace/metis
pip install -r app/requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 首次 /diagnose 触发 embedding 索引构建 (~18s, 一次性)
# 浏览器 http://localhost:8000/ 看 UI
```

**不要 API key 也能玩**（mock 模式）。但没有 ollama 也能跑——embedding 不可用时自动降级到纯关键词检索。

### 验证

```bash
curl http://localhost:8000/health
# 看 embed_ready 字段: true (有 ollama+bge-m3) / false (降级)
```

---

## 1. 改 KB 数据

适用场景：
- 修正某条 entry 的内容（summary / symptoms / actions 等）
- 加新 entry

### 步骤

```bash
# 1. 直接编辑 json 文件（8 个之一）
$EDITOR "Knowledge Base/0?-*.json"

# 2. 跑 audit
python3 scripts/audit_kb.py
# 应该 ALL CHECKS PASSED. No issues.

# 3. 重建索引 (kb-index.json 给 server 用)
python3 scripts/build_kb_index.py

# 4. 重建 prompt（inlines KB 内容到 prompt 里）
python3 scripts/build_prompt.py

# 5. 重启 server (★ v1.2: embedding index 重建需 18s, 启动后首次 /diagnose 慢)
kill $(cat /tmp/metis-server.pid)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
#   或: 用 /admin/reset 清缓存 (但 embedding_index 是服务启动时重建, 用 reset 反而会下次 /diagnose 重建)
#   实际推荐: 改 KB 后重启服务 (embedding_index 自动重建)
```

### 加新 entry 步骤

```bash
# 1. 编辑 json 文件, 加一条 entry (id 从 K111 开始)
# 2. 跑 audit (会自动检查 self-ref, dangling refs)
python3 scripts/audit_kb.py
# 3. 跑 retag, 让新 entry 至少有一个 v1 标签
#    可以直接编辑, 或用 LLM-assisted 重打
```

### 重打所有 111 条 v1 标签

```bash
# 1. 编辑 scripts/relabel_kb.py 里的 MAPPING
$EDITOR scripts/relabel_kb.py

# 2. dry-run
python3 scripts/relabel_kb.py --dry
# 看覆盖率报告 (v1 tag → entries 数)

# 3. apply
python3 scripts/relabel_kb.py

# 4. rebuild index + prompt + restart
python3 scripts/build_kb_index.py
python3 scripts/build_prompt.py
# (重启 server)
```

### 重写所有 111 条 action

类似 relabel，但跑 refactor_actions.py：

```bash
$EDITOR scripts/refactor_actions.py   # 改 ACTIONS dict
python3 scripts/refactor_actions.py     # apply
python3 scripts/audit_kb.py            # sanity check
python3 scripts/build_kb_index.py       # rebuild for server
# 重启 server
```

## 2. 调 Prompt

适用场景：
- LLM 经常发明 v1 外的标签
- LLM 输出 `actions` 字段
- LLM 不引用原话做 evidence
- 想给 LLM 更多 / 更少提示

### 步骤

```bash
# 1. 编辑 scripts/build_prompt.py 里的 HTML_TEMPLATE 字符串
$EDITOR scripts/build_prompt.py

# 2. 重新生成 prompt-v1.md
python3 scripts/build_prompt.py

# 3. 人读 prompt-v1.md 是否合理
#    - 25 个 v1 标签分类对吗?
#    - 6-7 条硬约束够严吗?
#    - KB 是否 inline 太多/太少?

# 4. 重启 server (uvicorn --reload 自动)
kill $(cat /tmp/metis-server.pid)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 5. 跑 [evaluation.md](evaluation.md) 至少 3 场景
#    - 高分命中 1 个 (期望稳定)
#    - 模糊命中 1 个 (期望少选)
#    - 边界 1 个 (期望跳错)

# 6. 失败案例记下, 复审 / 重写
```

### 复审 checklist（参见 [prompt.md](prompt.md) §6）

- LLM 发明 v1 外的标签
- LLM 输出 `actions` 字段
- LLM evidence 都是泛说（不是原话短语）
- LLM 容易选错标签（漏命中或过度命中）
- confidence 永远 0.9+

## 3. 加 1 个 v1 标签

适用场景：
- 真实用户反馈"这个状态没被识别"
- LLM 持续选 0 个导致 diagnoses 为空

### 步骤

```bash
# 1. 编辑 docs/taxonomy.md (§ 2 表格里加行)
$EDITOR docs/taxonomy.md

# 2. 编辑 scripts/relabel_kb.py 里的 V1_TAGS set
$EDITOR scripts/relabel_kb.py

# 3. 编辑 scripts/build_prompt.py 里的 CATEGORY_ORDER (加新标签到合适分类)
$EDITOR scripts/build_prompt.py

# 4. 加 KB 覆盖: 至少有 3-5 条 entry 用这个新标签
#    - 直接编辑 entry 的 diagnosis_tags 字段
#    或:
#    - 跑 scripts/relabel_kb.py 看新标签的 coverage 是 0, 然后你决定给哪些 KB 加这个标签

# 5. 重新生成
python3 scripts/relabel_kb.py
python3 scripts/build_kb_index.py
python3 scripts/build_prompt.py
python3 scripts/audit_kb.py
# 重启 server

# 6. 跑 5 段测试看新标签会不会被合理选中
```

参考 [taxonomy.md#扩展](taxonomy.md#扩展)。

## 4. 加新 API 端点

```bash
# 1. 编辑 app/main.py
$EDITOR app/main.py

# 2. 加 endpoint, 加 Pydantic models

# 3. 重启 server (uvicorn --reload)
kill $(cat /tmp/metis-server.pid)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 4. 更新 [api.md](api.md) + [app/README.md](../app/README.md)
$EDITOR docs/api.md
```

## 5. 部署

### 本地
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 公网（待补 Dockerfile + Render / Fly.io 配置）

TODO: 写 Dockerfile + fly.toml / render.yaml

## 6. 出错排查 (troubleshooting)

| 症状 | 检查 |
|---|---|
| `/diagnose` 返回 500 | 看 `/tmp/metis-server.log`；检查是否有 `DIFY_API_KEY` / 错误是 mock 还是真调用 |
| KB 看起来对不上 | 跑 `python3 scripts/audit_kb.py` |
| 服务起不来 | 检查端口占用 `lsof -i :8000` |
| actions 都是默认 3 个，没有真动作 | 检查 KB 里 `interventions` 是不是结构化对象（dict not str）。[scripts/refactor_actions.py](../scripts/refactor_actions.py) 一次性写好 |
| LLM 拒绝给 K-id | prompt 里 K-id 列表可能没显示，检查 prompts/build_prompt.py 的渲染 |
| 浏览器显示 spinner 不消失 | 大概率 LLM 调用挂了。看 server log |
| **`/diagnose` 返回 `400 invalid_param` from Dify** ★ v1.2 | **Dify workflow app 的输入变量名错配**。先在 Dify Studio 看自己 app 的输入变量名, 设 `DIFY_INPUT_VAR=<实际变量名>` 到 `.env` |
| **`embed_ready: false` 但服务能跑** ★ v1.2 | ollama 没启动或 bge-m3 没拉。检查 `ollama serve` + `ollama list`。降级到纯关键词检索不影响功能但 KB 检索精度下降 |
| **首次 `/diagnose` 慢 (~18s)** ★ v1.2 | embedding index 冷启动构建。第二次就快。如反复慢, 检查 `/admin/reset` 是否被频繁调用 |
| **`kb_hits` 不含期望 K-id** ★ v1.2 | KB 检索召回受限。检查 `embed_ready`；hybrid 默认 α=0.5 (平衡关键词与 embedding)。可手动调 `kb.search_hybrid(query, top_k=25, alpha=0.7)` 偏向 embedding |
| **深夜拿到"剧烈运动30分钟"** ★ v1.2 | 检查服务器时间是否在 22:00-06:00 之外 (如跨时区)。time_sensitive_filter 用服务器本地时间 |
| **Dify app 类型从 chat 改成 workflow 后不工作** ★ v1.2 | 调 `POST /admin/reset` 清 dify_mode_cache, 让服务端重探测 |

---

*整理于 2026-07-06 · v1.2 增量更新于 2026-07-07*
