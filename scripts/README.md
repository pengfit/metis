# Scripts

> 8 个 Python 脚本，每个做 1 件事。所有脚本都能 `python3 scripts/<name>.py` 直接跑。

## 目录

| 脚本 | 功能 | 何时跑 |
|---|---|---|
| `audit_kb.py` | 健康检查 111 条 KB | 改 KB 后必跑 |
| `relabel_kb.py` | 重打 111 条 KB 的 v1 标签 | 改 25 个 v1 标签时 |
| `refactor_actions.py` | 重写 KB 的 actions（概念名 → 动作动词） | 改动作规范时 |
| `tag_layers.py` | 给 111 条 KB 标 layer (method/mental-model/principle/theme) | 改层架构或加新 K-id 时 |
| `build_kb_index.py` | 生成 `kb-index.json`（tag → K-id 反向索引 + related 字段） | 改 KB 数据或标签后 |
| `build_prompt.py` | 生成 `prompt-v1.md`（LLM 输入用） | 改 prompt 模板或 KB 数据后 |
| `test_e2e.py` | FastAPI TestClient 端到端测试 | 改 server 代码或 schema 后 |
| `kb_to_graph.py` | v0 graph 实验脚本（仅 archive） | （不动，已 retire） |
| `_archive_graph_v1/` | v0 graph 实验的归档 | （不动） |

## 1. `audit_kb.py`

**功能**：健康检查

- 必填字段（id/name/category/summary）
- 占位条目 `[待补]`
- 跨文件 K-id 重复
- self-ref（related 含自己）
- 数组内重复
- 悬空引用（指向不存在的 K-id）
- graph.json / csv 同步（如果存在）

```bash
python3 scripts/audit_kb.py
# ✓ ALL CHECKS PASSED. No issues.
```

## 2. `relabel_kb.py`

**功能**：把每条 KB entry 的 `diagnosis_tags` 字段重写为 v1 标签格式

- 内置 V1_TAGS（25 个）
- 内置 MAPPING（111 条 entry × 1-3 个 v1 标签 + 0-2 个 free 标签）
- 写完打印覆盖率报告

```bash
python3 scripts/relabel_kb.py --dry    # 不写, 只看覆盖率
python3 scripts/relabel_kb.py          # 应用
```

## 3. `refactor_actions.py`

**功能**：把每条 KB entry 的 `interventions` 字段重写为结构化动作对象（5 字段）

- 内置 ACTIONS（111 条 × 3 动作 = 333 actions）
- 写完打印 when 分布

```bash
python3 scripts/refactor_actions.py     # 应用
```

## 4. `build_kb_index.py`

**功能**：从 JSON 读取，生成 `Knowledge Base/_eval/kb-index.json`

输出：
- `v1_taxonomy`: 25 个标签
- `v1_tag_to_kids`: tag → K-id 反向索引
- `free_tags`: free 标签 → K-ids
- `by_id`: K-id → entry 详情（含 interventions）

```bash
python3 scripts/build_kb_index.py
# Wrote ../Knowledge Base/_eval/kb-index.json  (109.3 KB)
```

## 5. `build_prompt.py`

**功能**：从 kb-index.json 生成 `prompt-v1.md`（24-28 KB, self-contained）

内嵌：
- 25 个 v1 标签分类表
- 111 个 KB 条目的 summary + actions preview

```bash
python3 scripts/build_prompt.py
# Wrote ../Knowledge Base/_eval/prompt-v1.md  (28.2 KB)
```

## 6. `test_e2e.py`

**功能**：用 FastAPI TestClient 端到端测 /diagnose + 校验 schema

- Mock LLM（用预制的 canned responses 模拟）
- 跑 8 个核心场景（S01/S02/S03/S08/S10 + 别的）
- 校验：confidence 范围 + actions 结构 + when 合法值
- 测完后说"真实 LLM 跑通只需 export OPENAI_API_KEY"

```bash
python3 scripts/test_e2e.py           # 跑全部
python3 scripts/test_e2e.py S08      # 只跑 S08
```

## 8. Pipeline（修改 KB 时的标准流程）

```bash
# 1. 编辑 KB JSON
$EDITOR "Knowledge Base/0?-*.json"

# 2. 选跑（看情况）
python3 scripts/audit_kb.py                # sanity check
python3 scripts/relabel_kb.py              # 如果改了 v1 标签
python3 scripts/refactor_actions.py        # 如果改了 interventions
python3 scripts/tag_layers.py             # 如果改了 layer 映射 (4 阶设计变了)

# 3. 必跑
python3 scripts/build_kb_index.py         # 重建索引
python3 scripts/build_prompt.py           # 重建 prompt

# 4. 重启 server
kill $(cat /tmp/metis-server.pid)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 5. 跑端到端测试
python3 scripts/test_e2e.py
```

---

*整理于 2026-07-06*
