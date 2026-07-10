"""LLM wrappers over any OpenAI-compatible endpoint (default: Gemini free tier; Groq works
by changing .env — see config.py). Fast model parses/routes (cheap), smart model only for
synthesis.

LLM budget per operation (RALLY-REVIEW.md section 5): shift parse = 1 fast call,
intake turn = 1 fast call, FAQ = 1 smart call, negotiation = 1 smart call.
Outreach, reminders, status updates: zero LLM calls.
"""
import json
import re
import time
from datetime import datetime

from openai import (APIConnectionError, InternalServerError, NotFoundError, OpenAI,
                    RateLimitError)

from rally import config

_client = None
# Retry/fallback triggers: 5xx overload, 429 rate limit, network, and 404 model-retired.
_TRANSIENT = (InternalServerError, RateLimitError, APIConnectionError, NotFoundError)


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    return _client


def _call(model: str, system: str, user: str, max_tokens: int, retries: int = 2) -> str:
    delay = 1.5
    for attempt in range(retries + 1):
        try:
            resp = client().chat.completions.create(
                model=model, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            return resp.choices[0].message.content or ""
        except _TRANSIENT as e:
            if attempt == retries:
                raise
            print(f"[llm] {model}: transient {type(e).__name__}; retry {attempt + 1}/{retries} in {delay:.1f}s")
            time.sleep(delay)
            delay *= 2


def _complete(model: str, system: str, user: str, max_tokens: int) -> str:
    """Retry transient errors (free-tier 503 spikes, 429) with backoff, then fall back to the
    other model tier if the requested one is persistently unavailable — a model outage must
    never break a user-facing answer."""
    try:
        return _call(model, system, user, max_tokens, retries=1)  # fail over fast on free tier
    except _TRANSIENT:
        alt = config.MODEL_FAST if model == config.MODEL_SMART else config.MODEL_SMART
        print(f"[llm] {model} unavailable after retries; falling back to {alt}")
        return _call(alt, system, user, max_tokens, retries=2)


def _json_block(raw: str) -> dict:
    """Extract the first JSON object from a model reply (tolerates ```json fences)."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in model reply: {raw[:200]}")
    return json.loads(raw[start : end + 1])


ROUTER_SYSTEM = """You route messages sent to Rally, a volunteer-coordination Slack agent.
Classify the user's message into exactly one intent:
- fill_shift: coordinator wants volunteers for a shift/event ("I need 6 volunteers Saturday...")
- intake: user wants to join/update the volunteer roster ("sign me up", "I can drive now")
- status: asking about shift coverage/roster status ("how's Saturday looking?")
- faq: a logistics/knowledge question ("where do I park?", "what should I bring?")
- my_data: privacy request ("show my info", "delete my data", "pause my volunteering")
- other: anything else
Reply with JSON only: {"intent": "..."}"""


def route(message: str) -> str:
    try:
        raw = _complete(config.MODEL_FAST, ROUTER_SYSTEM, message, 50)
        return _json_block(raw).get("intent", "other")
    except Exception:
        return "other"


PARSE_SHIFT_SYSTEM = """Extract a volunteer shift request into JSON. Today is {today} ({weekday}).
Fields:
- title: short name for the shift
- date: ISO date (resolve relative words like "Saturday" to the NEXT such day from today)
- start_time / end_time: "HH:MM" 24h (if only a start given, assume 3 hours)
- needed: integer headcount
- location: string or ""
- requirements: {{"certs": {{tag: count}}, "langs": {{tag: count}}}}
  cert tags: driver, first_aid, food_safety, forklift ; lang tags: es, hi, zh, fr
  Only include requirements the user actually stated.
Reply with JSON only. If it is not actually a shift request, reply {{"error": "not_a_shift"}}."""


def parse_shift_request(message: str) -> dict:
    today = datetime.now()
    system = PARSE_SHIFT_SYSTEM.format(today=today.strftime("%Y-%m-%d"), weekday=today.strftime("%A"))
    parsed = _json_block(_complete(config.MODEL_FAST, system, message, 400))
    if "error" in parsed:
        return parsed
    parsed.setdefault("requirements", {})
    parsed["starts_at"] = f"{parsed['date']}T{parsed['start_time']}"
    parsed["ends_at"] = f"{parsed['date']}T{parsed['end_time']}"
    return parsed


INTAKE_SYSTEM = """You are Rally's volunteer intake assistant for a nonprofit's Slack.
Goal: collect these fields through a SHORT, warm conversation (1 question per turn, bundle
related asks): availability (list of weekday_morning/weekday_afternoon/weekday_evening/
weekend_morning/weekend_afternoon/weekend_evening), certs (driver, first_aid, food_safety,
forklift — booleans stated by the user only), langs (es, hi, zh, fr beyond English), skills
(free tags like cooking, tutoring, admin).
Current known state: {state}
User's latest message: interpret it, update the state, then either ask the next question or,
if you have at least availability plus any one other signal, finish.
Reply with JSON only:
{{"say": "<your next message to the volunteer>",
 "state": {{...updated state...}},
 "done": true|false}}
When done=true, "say" must summarize what you recorded and ask them to tap Confirm."""


def intake_turn(state: dict, message: str) -> dict:
    system = INTAKE_SYSTEM.format(state=json.dumps(state))
    return _json_block(_complete(config.MODEL_FAST, system, message, 500))


FAQ_SYSTEM = """You answer a volunteer's logistics question using ONLY the search results
provided. Write the answer itself as plain text — NEVER put answer content inside a link
label. Then cite at the end like: (source: <permalink|#channel>) using ONLY permalinks that
appear in the results — never invent links. If the results don't contain the answer, say you
couldn't find it and that you've flagged it for a coordinator. Be brief and warm."""


def _norm_url(u: str) -> str:
    return u.split("?")[0].rstrip("/").lower()


def enforce_citation_whitelist(answer: str, allowed: set[str]) -> str:
    """Citation whitelist (RALLY-REVIEW.md, carried from REVIEW.md D7): a link may only
    survive if it appeared in the actual search results. Disallowed links keep their label
    text (content is never lost) but lose the URL."""
    allowed_n = {_norm_url(u) for u in allowed}
    out, i = [], 0
    while i < len(answer):
        if answer.startswith("<http", i):
            end = answer.find(">", i)
            if end == -1:
                out.append(answer[i:])
                break
            token = answer[i + 1 : end]
            url, _, label = token.partition("|")
            if _norm_url(url) in allowed_n:
                out.append(answer[i : end + 1])
            elif label:
                out.append(label)  # drop the bad URL, keep the human-readable text
            i = end + 1
        else:
            out.append(answer[i])
            i += 1
    return "".join(out)


_RAW_URL = re.compile(r"(?<!<)https?://\S+")


def faq_answer(question: str, search_results: list[dict]) -> str:
    allowed = {r.get("permalink") for r in search_results if r.get("permalink")}
    context = json.dumps(search_results[:8], indent=1)
    answer = _complete(config.MODEL_SMART, FAQ_SYSTEM,
                       f"Question: {question}\n\nSearch results:\n{context}", 600)
    answer = enforce_citation_whitelist(answer, allowed)
    # Raw (non-<>) URLs bypass the token check above — apply the same whitelist to them.
    allowed_n = {_norm_url(u) for u in allowed}
    return _RAW_URL.sub(
        lambda m: m.group(0) if _norm_url(m.group(0).rstrip(").,")) in allowed_n else "[link removed]",
        answer,
    )


NEGOTIATE_SYSTEM = """You are Rally, a volunteer-coordination agent. A shift cannot be filled
as specified. Given the shift, the shortfalls, and roster counts, propose 2-3 concrete
trade-off options for the coordinator (relax a requirement, reduce headcount, widen the pool
to volunteers outside their usual availability, or post an open call in a channel).
Be specific with numbers. Reply with JSON only:
{"summary": "<one-sentence diagnosis>",
 "options": [{"label": "<button label, max 5 words>", "description": "<one sentence>",
              "action": "relax_requirement|reduce_headcount|widen_pool|open_call",
              "params": {}}]}"""


def negotiate_options(shift: dict, shortfalls: list[dict], pool_size: int) -> dict:
    payload = json.dumps({"shift": {k: shift[k] for k in ("title", "starts_at", "needed", "requirements")},
                          "shortfalls": shortfalls, "eligible_pool_size": pool_size})
    return _json_block(_complete(config.MODEL_SMART, NEGOTIATE_SYSTEM, payload, 600))
