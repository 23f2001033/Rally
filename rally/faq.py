"""Cited FAQ answers. Primary path: Slack's Real-Time Search API (qualifying technology),
which needs an action_token from a user/mention event. Fallback path (no action_token, and
for sandboxes where RTS is restricted): read the channels Rally is a member of directly via
conversations.history and let the LLM synthesize with citations.

Policy compliance: results are used within this request only — never persisted, never
trained on (REVIEW.md D4). Citation whitelist enforced in llm.faq_answer."""
from rally import llm

# Channels Rally reads for the fallback path (it must be a member).
FALLBACK_CHANNELS = ("logistics", "volunteers", "events")
_channel_cache: dict[str, str] = {}


def _permalink(client, channel: str, ts: str) -> str:
    try:
        return client.chat_getPermalink(channel=channel, message_ts=ts)["permalink"]
    except Exception:
        return ""


def _rts_search(client, query: str, action_token: str) -> list[dict]:
    resp = client.api_call("assistant.search.context",
                           params={"query": query, "count": 8, "action_token": action_token})
    out = []
    for m in (resp.get("results") or {}).get("messages") or []:
        out.append({
            "text": (m.get("content") or m.get("text") or "")[:600],
            "channel": m.get("channel_id") or m.get("channel", ""),
            "author": m.get("author_user_id") or m.get("user", ""),
            "permalink": m.get("permalink", ""),
        })
    return out


def _channel_ids(client) -> dict[str, str]:
    if not _channel_cache:
        for c in client.conversations_list(limit=200, types="public_channel")["channels"]:
            if c.get("is_member"):
                _channel_cache[c["name"]] = c["id"]
    return _channel_cache


def _history_search(client, query: str) -> list[dict]:
    """Bot-token fallback: pull recent history from Rally's channels, keyword-rank, attach
    real permalinks. No action_token needed; uses channels:history scope."""
    terms = {w.lower().strip("?.,") for w in query.split() if len(w) > 3}
    scored = []
    for name in FALLBACK_CHANNELS:
        ch = _channel_ids(client).get(name)
        if not ch:
            continue
        for m in client.conversations_history(channel=ch, limit=50).get("messages", []):
            if m.get("subtype") or not m.get("text"):
                continue
            text = m["text"]
            score = sum(1 for t in terms if t in text.lower())
            if score:
                scored.append((score, {"text": text[:600], "channel": ch,
                                        "ts": m["ts"], "permalink": _permalink(client, ch, m["ts"])}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:8]]


def answer(client, question: str, action_token: str | None = None) -> str:
    results, source = [], "history"
    if action_token:
        try:
            results = _rts_search(client, question, action_token)
            source = "rts"
        except Exception as e:
            err = getattr(getattr(e, "response", None), "data", {}).get("error", str(e))
            print(f"[faq] RTS unavailable ({err}); falling back to channel history")
    if not results:
        try:
            results = _history_search(client, question)
        except Exception as e:
            return (":mag: I couldn't search the workspace just now. Try again in a moment, "
                    "or ask a coordinator in #volunteers.")
    if not results:
        return (":mag: I couldn't find that in our workspace history. I'd suggest asking in "
                "#volunteers — once it's answered there, I'll be able to find it next time.")
    print(f"[faq] answered via {source} with {len(results)} results")
    return llm.faq_answer(question, results)
