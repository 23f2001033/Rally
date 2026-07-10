"""Conversational volunteer intake: short guided chat -> confirmed structured roster entry.
Free text is normalized to controlled tags and echoed back for confirmation
(RALLY-REVIEW.md R4) — only human-confirmed structure is stored."""
import json

from rally import blocks, db, llm


def get_session(conn, user_id: str) -> dict:
    row = conn.execute(
        "SELECT state FROM intake_sessions WHERE slack_user_id = ?", (user_id,)
    ).fetchone()
    return json.loads(row["state"]) if row else {}


KNOWN_CERTS = {"driver", "first_aid", "food_safety", "forklift"}
KNOWN_LANGS = {"es", "hi", "zh", "fr"}
AVAIL_TAGS = {f"{d}_{t}" for d in ("weekday", "weekend")
              for t in ("morning", "afternoon", "evening")}


def normalize_state(state: dict) -> dict:
    """Models are inconsistent about shape: they may return {'certs': {'driver': true}},
    a bare string, or hoist a tag like 'driver': true to the TOP level. Coerce everything to
    lists of truthy tags and re-home stray known tags into the right bucket, so matching
    semantics stay consistent regardless of the model's whims."""
    out = dict(state or {})
    buckets = {"availability": [], "certs": [], "langs": [], "skills": []}

    def as_tags(val):
        if isinstance(val, dict):
            return [k for k, v in val.items() if v]
        if isinstance(val, str):
            return [val]
        return list(val or [])

    for key in buckets:
        buckets[key] = as_tags(out.get(key))

    # Hoist stray top-level known tags (e.g. {"driver": true}) into their bucket.
    for key in list(out.keys()):
        if key in buckets:
            continue
        truthy = out[key] if isinstance(out[key], bool) else bool(out[key])
        if key in KNOWN_CERTS and truthy:
            buckets["certs"].append(key)
        elif key in KNOWN_LANGS and truthy:
            buckets["langs"].append(key)
        elif key in AVAIL_TAGS and truthy:
            buckets["availability"].append(key)

    return {k: sorted(set(v)) for k, v in buckets.items()}


def save_session(conn, user_id: str, state: dict) -> None:
    state = normalize_state(state)
    conn.execute(
        "INSERT INTO intake_sessions (slack_user_id, state, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(slack_user_id) DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at",
        (user_id, json.dumps(state), db.now_iso()),
    )
    conn.commit()


def clear_session(conn, user_id: str) -> None:
    conn.execute("DELETE FROM intake_sessions WHERE slack_user_id = ?", (user_id,))
    conn.commit()


def handle_turn(client, conn, user_id: str, message: str, say) -> None:
    state = get_session(conn, user_id)
    result = llm.intake_turn(state, message)
    new_state = normalize_state(result.get("state", state))
    save_session(conn, user_id, new_state)
    if result.get("done"):
        say(text="Confirm your volunteer profile",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": result["say"]}}]
                   + blocks.intake_confirm_blocks(new_state))
    else:
        say(text=result["say"])


def confirm(client, conn, user_id: str) -> str:
    state = get_session(conn, user_id)
    try:
        info = client.users_info(user=user_id)
        name = (info["user"].get("real_name") or info["user"]["name"])
    except Exception:
        name = user_id
    conn.execute(
        """INSERT INTO volunteers (slack_user_id, name, skills, certs, langs, availability,
                                   active, is_simulated, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)
           ON CONFLICT(slack_user_id) DO UPDATE SET
             skills = excluded.skills, certs = excluded.certs, langs = excluded.langs,
             availability = excluded.availability, active = 1""",
        (user_id, name,
         json.dumps(state.get("skills") or []), json.dumps(state.get("certs") or []),
         json.dumps(state.get("langs") or []), json.dumps(state.get("availability") or []),
         db.now_iso()),
    )
    conn.commit()
    clear_session(conn, user_id)
    return name


def my_data(conn, user_id: str, message: str) -> str:
    """Privacy self-service (RALLY-REVIEW.md R9)."""
    lowered = message.lower()
    row = conn.execute("SELECT * FROM volunteers WHERE slack_user_id = ?", (user_id,)).fetchone()
    if "delete" in lowered:
        if row:
            conn.execute("DELETE FROM assignments WHERE volunteer_id = ?", (row["id"],))
            conn.execute("DELETE FROM hours_ledger WHERE volunteer_id = ?", (row["id"],))
            conn.execute("DELETE FROM volunteers WHERE id = ?", (row["id"],))
            conn.commit()
            return ":wastebasket: Done — your volunteer record and history are deleted. Thanks for everything you gave!"
        return "You don't have a volunteer record with me."
    if "pause" in lowered:
        if row:
            conn.execute("UPDATE volunteers SET active = 0 WHERE id = ?", (row["id"],))
            conn.commit()
            return ":pause_button: Paused — I won't reach out until you say \"resume my volunteering\"."
        return "You don't have a volunteer record with me."
    if "resume" in lowered and row:
        conn.execute("UPDATE volunteers SET active = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        return ":arrow_forward: Welcome back! You're active again."
    if row:
        v = db.row_to_volunteer(row)
        hours = conn.execute(
            "SELECT COALESCE(SUM(hours), 0) h FROM hours_ledger WHERE volunteer_id = ?", (v["id"],)
        ).fetchone()["h"]
        return (f":clipboard: *Your record:*\n• Availability: {', '.join(v['availability']) or '—'}\n"
                f"• Certifications: {', '.join(v['certs']) or '—'}\n"
                f"• Languages: {', '.join(v['langs']) or '—'}\n"
                f"• Skills: {', '.join(v['skills']) or '—'}\n"
                f"• Hours contributed: {hours:g}\n"
                "_Say \"delete my data\" or \"pause my volunteering\" anytime._")
    return "You don't have a volunteer record yet — say *\"I'd like to volunteer\"* to join!"
