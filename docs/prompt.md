# 诊断 Prompt

> 系统给 LLM 的指令模板。它规定 LLM 在 /diagnose 调用时该做什么、不该做什么。
>
> 源文件：`Knowledge Base/_eval/prompt-v1.md`（机器生成）
> 锁定 v1 · 2026-07-06

## 1. 职责边界

**LLM 只做 2 件事：**
1. 从 25 个 v1 标签里选 1-3 个最匹配的
2. 从 KB 里挑出 1-3 个最相关的 K-id

**服务端做 2 件事：**
1. 校验 LLM 输出（防幻觉）
2. 从 K-id 拉真实结构化 actions

这条分工是核心防幻觉机制。LLM 不知道 action 的字段细节，所以也写不出来（写出来也是错的）。

## 2. Prompt 文件位置与生成

- 源文件：`Knowledge Base/_eval/prompt-v1.md`（27KB，自包含）
- 生成器：[scripts/build_prompt.py](../scripts/build_prompt.py)
- 输入：`Knowledge Base/_eval/kb-index.json`
- 输出：`prompt-v1.md`

**改动 prompt 时：**
- 改 `scripts/build_prompt.py` 里的字符串模板
- 跑 `python3 scripts/build_prompt.py` 重生成
- 重启 FastAPI 服务（uvicorn 自动 reload 也行）

## 3. 6 条硬约束

```
1. 只能从 25 个 v1 标签中选 1-3 个
2. 宁少勿真（diagnoses: [] 合法）
3. 用户语言 → 标签（不要反向匹配 KB 概念）
4. 每诊断必有 evidence（用户原话短语）
5. k_ids 必须真实存在（错的丢）
6. 不输出 interventions/actions（服务端拉）
7. 不给建议（只诊断，不写"你该怎么做"）
```

第 7 条是边界保护：LLM 不该越界当治疗师。

## 4. 输出 Schema（LLM 必须严格按这个输出）

```json
{
  "diagnoses": [
    {
      "tag":        "<v1 标签>",
      "confidence": <0.0–1.0>,
      "evidence":   "<用户原话短语>",
      "k_ids":      ["<K-id>", "..."]
    }
  ],
  "notes":    "<一句话整体说明>",
  "fallback": "<诊断为空时填>"
}
```

具体字段：
- `confidence`: 0=完全不该是这个, 1=几乎确定。0.5=可能有别解。< 0.4=勉强
- `diagnoses`: ≤ 3 个，超过砍到最强 3 个
- `k_ids`: 1-4 个，按相关度排序
- `evidence`: 引用用户原话中具体短语，不要泛说

## 5. KB 上下文（外部检索 + 内嵌并存）

**v1.2 变更（2026-07-07）：** KB 进“理解”那一刀, **hybrid 检索已实装**。

之前 prompt 内嵌 KB 静态信息（25 标签表 + 111 K-id 预览），让 LLM 盲选。  
现在 **服务端在调用 LLM 前先 hybrid 检索**（关键词 × ollama bge-m3 cosine），把 top-25 候选 K-id + 摘要拼成 `<<KB_CONTEXT>>` 块送入。

两条路径同时存在：
- **外部 hybrid 检索**（v1.2 主路径）：`kb.search_hybrid(query)` → top-25 → LLM 看候选
- **内嵌静态表**（保底）：prompt 里仍嵌入 25 标签表 + 111 K-id 摘要，保证 Dify 端独立运行不被服务端拖累

```
<USER_INPUT>            ← 用户原文
<</USER_INPUT>>

<<KB_CONTEXT>>           ← 服务端 kb.context_for() 注入
以下是从知识库检索出的最相关条目。请在候选 tag + k_ids 中判断。
evidence 必须引用下方【摘要】或【动作预览】中的具体短语，不要泛说。

- [K019] 想象 | tag候选: 焦虑 / 反刍 / mental simulation / 想象练习 | 相关度: 5.0
  【摘要】想象是低成本的预演；也是焦虑的放大镜。
  【动作预览】具体场景想象1次 · 设'想象界限' · 物理切断预演
...
<</KB_CONTEXT>>
```

设计原因：
- **候选集减少**：从 25 tag × 111 K-id 盲选 → top-25 候选，LLM 选错空间压缩
- **evidence 可控**：KB context 明示“引用【摘要】短语”，LLM 不再泛说
- **上下文透明**：响应里带 `kb_hits` 字段，前端可展示“哪些 KB 条目参与了这次诊断”

服务端调用逻辑（`app/main.py`）：
```python
kb_hits = kb.search_hybrid(req.input, top_k=15)           # ★ v1.2: hybrid 检索
kb_context = kb.context_for_from_hits(kb_hits)            # 不重复跑 search
raw = await llm.call_llm(req.input, kb_context=kb_context)
```

Dify 端如何接收 KB context：
- **chat-messages 模式**：拼到 `query` 字段，同时塞 `inputs.kb_context` 供 prompt 模板 `{kb_context}` 引用
- **workflow 模式**：拼到 `inputs[USER_DESCRIPTION]`，同时塞 `inputs.KB_CONTEXT` 变量

## 6. 怎么迭代 Prompt

### 该改 Prompt 的征兆

| 症状 | 改什么 |
|---|---|
| LLM 经常发明 v1 外的标签 | 强化约束 1 的措辞 |
| LLM 输出 `actions` 字段 | 强化约束 6 的措辞 |
| confidence 给得都 0.9+ | 加示例说明置信度梯度 |
| evidence 都是泛说 | 强化约束 4 |
| 漏掉 K-id（用户描述明显命中但 LLM 没找到） | 在标签的映射里加更多 K-id 提示 |
| 选 1 个 tag 时容易选错 | 在每个标签的"口语定义"里加更多反例 |

### 怎么测

每次改 prompt，至少跑 [docs/evaluation.md](evaluation.md) 里至少 3 个场景：
- 1 个高分命中（应稳定）
- 1 个模糊命中（应"宁少勿真"地少选）
- 1 个边界场景（应跳过非 v1 的"概念名"）

可对比改前 / 改后的输出。

### 复审频率

- **第 10 次 /diagnose 调用后**：粗看 5 个真实输出
- **每月 1 次**：完整跑 [evaluation.md](evaluation.md) 10 场景
- **任何标签扩展时**：必跑

## 7. 常见问题 FAQ

### Q: 为什么不让 LLM 写 `interventions`?
A: 防幻觉。让 LLM 写 "5秒法则" 是 OK，但让它写 "倒数5秒立刻打开文档输入第一句" 这个**具体动作**它常编出不存在的方法。KB 里已经存好 333 个真实动作。让服务端读 KB 是 ground truth。

### Q: 为什么不让 LLM 引用 KB 外的 K-id?
A: _validate 会过滤掉，但 prompt 已经写了约束 5"必须真实存在",LLM 默认会遵守。

### Q: 为什么 confidence 不是必填?
A: 是的（不填会被默认 0.5）。这是反幻觉让 LLM 自由表达不确定度。

### Q: 能不能让 LLM 输出 ranking 顺序,而不是 confidence 分数?
A: 目前是排序 + 置信度并行。排名由 prompts 的 K-id 顺序隐含。

### Q: tag 选多了会怎样?
A: 不会强制 3 个，但 prompt 强约束"宁少勿真"，LLM 默认 1-3。  
   服务端会接受任意 ≤3 个，超过自动砍到最强 3 个（按 confidence 排序）。

### Q: LLM 输出 markdown 代码块怎么办?
A: OpenAI 的 `response_format={"type": "json_object"}` 强制 JSON 模式。Anthropic 偶有 ``` 包裹, llm.py 会自动剥离。

### Q: KB search 召回差怎么办（用户描述的是症状, KB name 是术语）?
A: v1.2 已上 hybrid 检索（关键词 + embedding cosine 融合）：
  1. `kb.search_hybrid(query, top_k=25, alpha=0.5)` —— 关键词 × ollama bge-m3 1024-dim cosine 融合
  2. `top_k=25` 给 LLM 充足候选, 它自己有语义判断
  3. `kb_hits` 字段返回到响应, 前端可展示/调试
  4. ollama 不可用时自动降级到纯关键词检索, `embed_ready=false` 标记

实测（S01/S03/S08/S10 四场景）hybrid 召回改善明显: S01/S10 完全召回期望 K-id；S03 召回 K019；S08 K014/K005 是抽象概念 KB 名称与用户描述鸿沟仍存在, 但 LLM 在 KB context 候选里自己挑对了标签。

---

## 8. 多轮 / 对话模式（待定）

当前 prompt 是单轮（一次输入→一次输出）。多轮（用户继续描述、追问）会需要：
- 把上次的 diagnoses + notes 加入 system prompt context
- 让 LLM 决定"在已有诊断基础上扩展"还是"识别到新标签"

这块没做。需要时再扩展 prompt + 服务端路由。

---

## 9. v1.2 增量小结

- **hybrid KB 检索实装**（关键词 × ollama bge-m3 cosine）
- top_k 从 15 调到 25（给 LLM 更大候选空间）
- Dify prompt 强调"evidence 必须引 KB 短语"（C 方案核心）
- ollama 不可用时降级到纯关键词检索（`embed_ready=false`）
- 详见 [architecture.md](architecture.md) §2 数据流 + [api.md](api.md) §4 kb_hits/time_context

---

*整理于 2026-07-06 · v1.2 更新于 2026-07-07*
