"""LLM client abstraction — Dify only.

Reads system prompt from `Knowledge Base/_eval/prompt-v1.md` at startup,
sends user input via Dify Chat Messages API, parses JSON, returns raw dict
for app.main validation.

Provider resolution:
  1. `LLM_PROVIDER` env defaults to "dify" (the only real provider)
  2. MOCK=1 env wins (test mode) — uses canned responses

Mock fallback: when DIFY_API_KEY not set AND MOCK!=1, return canned JSON
with `[MOCK 自动]` banner.

Dify provider notes:
  - Dify 用 app 自配置的 prompt, 我们不传 system prompt (被忽略)
  - 端点: POST {DIFY_API_BASE}/chat-messages (blocking 模式)
  - 期望 Dify app 的响应 `answer` 字段是符合诊断 schema 的 JSON
  - 配置 Dify app 时, 把 `Knowledge Base/_eval/prompt-v1.md` 的指导嵌入 app prompt
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from functools import lru_cache

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE.parent / "Knowledge Base" / "_eval" / "prompt-v1.md"

DEFAULT_MODELS = {
    "dify": os.environ.get("DIFY_MODEL", "dify-app"),
}


class MissingAPIKeyError(Exception):
    pass


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Prompt not found at {PROMPT_PATH}. "
            "Run `python3 scripts/build_prompt.py` first."
        )
    text = PROMPT_PATH.read_text(encoding="utf-8")
    start = text.find("## <role-and-rules>")
    end = text.find("</role-and-rules>")
    if start < 0 or end < 0:
        raise RuntimeError("prompt-v1.md missing <role-and-rules> markers")
    start += len("## <role-and-rules>")
    return text[start:end].strip()


def user_message(user_input: str, kb_context: str | None = None) -> str:
    """构造送进 LLM 的 user message。kb_context 由 KB 检索生成 (见 kb.context_for)。"""
    parts = [f"<<USER_INPUT>>\n{user_input.strip()}\n<</USER_INPUT>>"]
    if kb_context:
        parts.append(kb_context)
    return "\n".join(parts)


def resolve_provider(provider: str | None, model: str | None) -> tuple[str, str]:
    p = (provider or os.environ.get("LLM_PROVIDER", "dify")).lower()
    if p not in DEFAULT_MODELS:
        raise ValueError(
            f"Unknown provider: {p!r}. The only real provider now is 'dify' "
            f"(use 'openclaw'/'openai'/'anthropic' was retired)."
        )
    m = model or os.environ.get("LLM_MODEL", DEFAULT_MODELS[p])
    return p, m


def _any_provider_configured() -> bool:
    """True when Dify is configured."""
    return bool(os.environ.get("DIFY_API_KEY"))


async def call_llm(
    user_input: str,
    provider: str | None = None,
    model: str | None = None,
    *,
    kb_context: str | None = None,
) -> dict:
    """Call Dify, return raw parsed JSON dict. Validators in app.main clean it.

    Order:
      1. MOCK=1 env → canned (wins always)
      2. DIFY_API_KEY set → real Dify call
      3. Else → silent fallback to mock with banner in notes

    Args:
        kb_context: KB 检索输出的 context 块 (见 kb.context_for)。
                    若提供, 会拼到 query (chat 模式) 或 inputs (workflow 模式) 里送出去。
                    Mock 模式忽略此参数 (mock 不读 KB context)。
    """
    if os.environ.get("MOCK") == "1" or os.environ.get("METIS_MOCK") == "1":
        return _mock_response(user_input, tag="[MOCK 强制]")
    if provider is None and not _any_provider_configured():
        return _mock_response(user_input, tag="[MOCK 自动] 未检测到 DIFY_API_KEY, 使用预制响应")
    p, _m = resolve_provider(provider, model)
    if p == "dify":
        for attempt in range(2):
            try:
                return await _call_dify(user_input, kb_context=kb_context)
            except ValueError as e:
                # 重试条件: JSON 解析失败 或 Dify workflow 输出 schema 校验失败
                # (后者是 Dify LLM 节点间歇性产出非纯 JSON 触发的, 重试通常能过)
                msg = str(e)
                if attempt == 0 and (
                    "LLM 输出不是合法 JSON" in msg
                    or "Dify workflow 报错" in msg
                ):
                    continue
                raise
    raise ValueError(f"Provider branch missing: {p}")


def _mock_response(user_input: str, tag: str = "[MOCK]") -> dict:
    """Canned LLM-style response for testing without Dify API.

    Keyed on simple Chinese keyword matching. Falls back to a generic response.
    """
    s = user_input
    if ("拖" in s and ("写不出" in s or "开头" in s or "完美" in s)):
        return {
            "diagnoses": [
                {"tag":"拖延","confidence":0.92,"evidence":"拖了/写不出/开头","k_ids":["K035","K036"]},
                {"tag":"完美主义","confidence":0.74,"evidence":"开头不够惊艳","k_ids":["K036"]},
            ],
            "notes": f"{tag} 拖延+完美主义路径",
        }
    if ("升职" in s or "面谈" in s or "面试" in s) and ("想" in s or "停" in s or "搞砸" in s):
        return {
            "diagnoses": [
                {"tag":"反刍","confidence":0.93,"evidence":"停不下来","k_ids":["K019","K020"]},
                {"tag":"焦虑","confidence":0.86,"evidence":"越想越糟","k_ids":["K032","K019"]},
            ],
            "notes": f"{tag} 反刍+焦虑路径",
        }
    if ("11" in s and "手机" in s) or ("废" in s and "自责" in s):
        return {
            "diagnoses": [
                {"tag":"信念冲突","confidence":0.86,"evidence":"理性知道但停不下来","k_ids":["K014","K005"]},
                {"tag":"极端思维","confidence":0.71,"evidence":"全盘放弃","k_ids":["K020","K004"]},
            ],
            "notes": f"{tag} 信念冲突路径",
        }
    if ("朋友" in s and "血脂" in s) or ("留下来" in s) or ("死亡" in s) or ("尽头" in s):
        return {
            "diagnoses": [
                {"tag":"死亡焦虑","confidence":0.93,"evidence":"想到有限性","k_ids":["K110"]},
                {"tag":"意义缺失","confidence":0.81,"evidence":"没留下来","k_ids":["K031","K039"]},
            ],
            "notes": f"{tag} 死亡+意义路径",
        }
    if ("累" in s or "疲惫" in s) and ("在为谁" in s or "空虚" in s or "没充电" in s):
        return {
            "diagnoses": [
                {"tag":"疲惫","confidence":0.88,"evidence":"休息不恢复","k_ids":["K051","K025","K057"]},
                {"tag":"空虚","confidence":0.79,"evidence":"无意义感","k_ids":["K012","K039","K031"]},
            ],
            "notes": f"{tag} 疲惫+空虚路径",
        }
    if "边界" in s or "说不" in s or "被动" in s:
        return {
            "diagnoses": [
                {"tag":"边界模糊","confidence":0.83,"evidence":"说不出口","k_ids":["K034","K097","K107"]},
                {"tag":"被动等待","confidence":0.61,"evidence":"等他来","k_ids":["K002","K050"]},
            ],
            "notes": f"{tag} 边界+被动路径",
        }
    return {
        "diagnoses": [
            {"tag":"疲惫","confidence":0.5,"evidence":"[mock 通用] 描述不充分匹配任何具体路径","k_ids":["K051","K025"]},
        ],
        "notes": f"{tag} 设置 DIFY_API_KEY 关掉 MOCK 看真实 LLM 输出",
    }


async def _call_dify(user_input: str, kb_context: str | None = None) -> dict:
    """Dify provider — auto-detect chat vs workflow app, fall back as needed.

    试 chat-messages (/v1/chat-messages) → 收到 400 "not_chat_app" → 试
    workflows/run (/v1/workflows/run).
    结果缓存, 后调直接走对路径.

    Configuration:
      DIFY_API_KEY   app 的 API key (必须)
      DIFY_API_BASE  端点根 (默认 https://api.dify.ai/v1)
      DIFY_APP_ID    可选, 人类可读名 (存于 inputs.app_id 作记录)
      DIFY_USER      可选, user id (默认 "metis")

    Workflow outputs 可能是 JSON object 或 string. 两者都处理.

    kb_context 传递策略:
      - chat 模式: 拼到 query 字段 (LLM 直接看到), 同时塞 inputs.kb_context
        供 Dify prompt 模板引用 (可选)
      - workflow 模式: 拼到 USER_DESCRIPTION (主路径), 同时塞 KB_CONTEXT 变量
        (供 Dify prompt 引用, 不影响现有 prompt)
    """
    api_key = os.environ.get("DIFY_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "DIFY_API_KEY 未设置. 请在 app/.env 或环境变量中配置 Dify app key.\n"
            "或在请求 body 里指定 provider='mock'(或设 MOCK=1) 走预制响应."
        )
    base_url = os.environ.get("DIFY_API_BASE", "https://api.dify.ai/v1").rstrip("/")
    app_id = os.environ.get("DIFY_APP_ID", "")
    user_id = os.environ.get("DIFY_USER", "metis")
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }

    # 优先走缓存中的路径
    cached = _dify_mode_cache.get("mode")
    if cached == "chat":
        return await _dify_chat(base_url, headers, user_input, user_id, app_id, kb_context)
    if cached == "workflow":
        return await _dify_workflow(base_url, headers, user_input, user_id, kb_context)

    # 没缓存 — 先试 chat
    try:
        result = await _dify_chat(base_url, headers, user_input, user_id, app_id, kb_context)
        _dify_mode_cache["mode"] = "chat"
        return result
    except httpx.HTTPStatusError as e:
        body_text = (e.response.text or "").lower()
        if e.response.status_code == 400 and "not_chat_app" in body_text:
            # 不是 chat app, 切到 workflow
            _dify_mode_cache["mode"] = "workflow"
            return await _dify_workflow(base_url, headers, user_input, user_id, kb_context)
        raise


async def _dify_chat(base_url, headers, user_input, user_id, app_id, kb_context=None) -> dict:
    """Dify Chat Messages API (POST /chat-messages)."""
    inputs: dict = {"app_id": app_id} if app_id else {}
    if kb_context:
        inputs["kb_context"] = kb_context  # 供 Dify prompt 模板 {kb_context} 引用

    query_text = user_input.strip()
    if kb_context:
        # 主路径: 直接拼到 query, LLM 立刻看到 KB 候选
        query_text = query_text + "\n\n" + kb_context

    payload = {
        "inputs":  inputs,
        "query":   query_text,
        "user":    user_id,
        "response_mode": "blocking",
    }
    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base_url}/chat-messages", json=payload, headers=headers)
        r.raise_for_status()
        body = r.json()
    answer = (body.get("answer") or "").strip()
    if not answer:
        raise ValueError(f"Dify chat 响应无 answer 字段: {body}")
    return _parse(answer)


async def _dify_workflow(base_url, headers, user_input, user_id, kb_context=None) -> dict:
    """Dify Workflow Run API (POST /workflows/run).

    workflow app 接收 inputs dict (变量映射), 输出在 body.data.outputs.

    输入变量名通过 `DIFY_INPUT_VAR` 选 (默认 "USER_DESCRIPTION", 适配常见诊断场景;
    可通过环境变量上调为别的名, 例 "query")。

    kb_context 处理:
      - 主路径: 拼到 USER_DESCRIPTION 末尾 (不依赖 Dify prompt 改)
      - 副路径: 同时塞 KB_CONTEXT 变量供 Dify prompt 模板 {KB_CONTEXT} 引用
    """
    input_var = os.environ.get("DIFY_INPUT_VAR", "USER_DESCRIPTION")
    inputs: dict = {input_var: user_input}
    if kb_context:
        inputs[input_var] = user_input + "\n\n" + kb_context
        inputs["KB_CONTEXT"] = kb_context
    payload = {
        "inputs": inputs,
        "user":  user_id,
        "response_mode": "blocking",
    }
    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base_url}/workflows/run", json=payload, headers=headers)
        r.raise_for_status()
        body = r.json()

    data = body.get("data") or {}
    if data.get("error"):
        raise ValueError(f"Dify workflow 报错: {data['error']}")
    outputs = data.get("outputs")
    if outputs is None:
        outputs = body.get("outputs", body)
    if outputs is None:
        raise ValueError(f"Dify workflow 响应无 outputs: {body}")

    if isinstance(outputs, str):
        return _parse(outputs)
    if isinstance(outputs, dict):
        # Dify workflow 经常嵌套 {"result": {"diagnoses": [...]}} 这类一层包装
        # 先 unwrap 一个常见包装键, 再判断 schema。
        for wrapper in ("result", "data", "output", "answer", "text"):
            inner = outputs.get(wrapper)
            if isinstance(inner, dict) and isinstance(inner.get("diagnoses"), list):
                outputs = inner
                break
        # Dify workflow 有时会把诊断 JSON 塞在 {"text": "<json string>"}
        if outputs and "diagnoses" not in outputs:
            string_vals = [v for v in outputs.values() if isinstance(v, str)]
            if string_vals:
                # 试拼所有字符串值 (多个 LLM 输出取拼接)
                return _parse("\n".join(string_vals))
        return outputs
    raise ValueError(f"Dify workflow outputs 类型意外: {type(outputs).__name__} = {outputs!r}")


# Module-level cache: 一但探测到, 后续走同样的路径
_dify_mode_cache: dict[str, str] = {}


def _parse(content: str) -> dict:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Strip ```json ... ``` if present
        if "```" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        raise ValueError(f"LLM 输出不是合法 JSON: {content[:200]!r}")
