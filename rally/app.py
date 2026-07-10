"""Rally — Bolt entrypoint. Socket Mode for dev/sandbox; every trigger is on-demand
(DM, mention, button, or a due job Rally itself scheduled). No ambient channel reading.

Run: python -m rally.app
"""
import re
import time
from datetime import datetime, timedelta, timezone

from slack_bolt import App, Assistant, Say, SetStatus, SetSuggestedPrompts
from slack_bolt.adapter.socket_mode import SocketModeHandler

from rally import (blocks, canvas, config, db, faq, intake, llm, matching,
                   negotiate, outreach, scheduler, simulation)

# Placeholder token keeps the module importable without credentials (tests/CI);
# with real credentials, verification runs at startup and fails fast on a bad token.
app = App(
    token=config.SLACK_BOT_TOKEN or "xoxb-placeholder",
    token_verification_enabled=bool(config.SLACK_BOT_TOKEN),
)
assistant = Assistant()

WELCOME = (":wave: Hi, I'm *Rally* — your volunteer coordination agent.\n"
           "• Coordinators: describe a shift and I'll fill it.\n"
           "• Volunteers: say *\"I'd like to volunteer\"* to join the roster.\n"
           "• Anyone: ask logistics questions — I'll answer with sources.")

SUGGESTED = [
    {"title": "Fill a shift",
     "message": "I need 6 volunteers for the Saturday food drive, 9am-1pm at the warehouse. At least 2 with driver's licenses and 1 Spanish speaker."},
    {"title": "Join as a volunteer", "message": "I'd like to sign up as a volunteer."},
    {"title": "Coverage status", "message": "How's coverage looking for our upcoming shifts?"},
    {"title": "Ask a question", "message": "Where do I park at the warehouse?"},
]


def _status_summary(conn) -> str:
    rows = conn.execute(
        "SELECT * FROM shifts WHERE status IN ('open','filled') ORDER BY starts_at LIMIT 10"
    ).fetchall()
    if not rows:
        return "No upcoming shifts on the books. Describe one and I'll staff it!"
    lines = [":calendar: *Upcoming shifts:*"]
    for r in rows:
        s = db.row_to_shift(r)
        p = matching.shift_progress(conn, s["id"])
        icon = ":white_check_mark:" if s["status"] == "filled" else ":hourglass_flowing_sand:"
        lines.append(f"{icon} *{s['title']}* — {blocks.fmt_when(s)} — "
                     f"{len(p['accepted'])}/{s['needed']} confirmed")
    return "\n".join(lines)


def _handle_fill_request(client, conn, text: str, user_id: str, say,
                         channel_id: str | None = None, thread_ts: str | None = None) -> None:
    parsed = llm.parse_shift_request(text)
    if "error" in parsed:
        say(text="Tell me what you need like: *\"I need 6 volunteers Saturday 9am-1pm at the "
                 "warehouse, 2 with driver's licenses\"* and I'll take it from there.")
        return
    shift = outreach.create_shift(conn, parsed, user_id, channel_id, thread_ts)
    plan = matching.plan_invites(conn, shift)
    if not plan["invite"]:
        say(text=f"I logged *{shift['title']}* but found no eligible volunteers — let's figure out options.")
        negotiate.propose(client, conn, shift, plan["shortfalls"])
        return
    n = outreach.send_invites(client, conn, shift, plan["invite"])
    say(text=(f":rocket: On it — *{shift['title']}* needs {shift['needed']}. I've reached out to "
              f"{n} matching volunteer{'s' if n != 1 else ''}"
              + (" (requirements prioritized)" if shift["requirements"] else "")
              + ". Live status below — I'll escalate if we run short."))
    shift = outreach.get_shift(conn, shift["id"])
    outreach.post_or_update_status_card(client, conn, shift)
    canvas.upsert(client, conn, shift)
    if not plan["feasible"]:
        negotiate.propose(client, conn, shift, plan["shortfalls"])
    db.add_job(conn, "fill_check",
               (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(timespec="seconds"),
               {"shift_id": shift["id"]})


def _route_and_handle(client, conn, text: str, user_id: str, say, set_status=None,
                      channel_id=None, thread_ts=None, action_token=None) -> None:
    sim_match = re.search(r"simulate a? ?cancell?ation", text, re.I)
    if sim_match and config.SIMULATION:
        row = conn.execute(
            "SELECT id FROM shifts WHERE status IN ('filled','open') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            name = simulation.cancel_random_accepted(client, conn, row["id"])
            say(text=f"🤖 Simulated: *{name}* just cancelled — watch me fix it." if name
                else "No simulated confirmed volunteers to cancel right now.")
        else:
            say(text="No active shift to simulate a cancellation on.")
        return

    if intake.get_session(conn, user_id):
        intake.handle_turn(client, conn, user_id, text, say)
        return

    if set_status:
        set_status("thinking…")
    intent = llm.route(text)
    if intent == "fill_shift":
        if set_status:
            set_status("matching volunteers…")
        _handle_fill_request(client, conn, text, user_id, say, channel_id, thread_ts)
    elif intent == "intake":
        intake.save_session(conn, user_id, {})
        intake.handle_turn(client, conn, user_id, text, say)
    elif intent == "status":
        say(text=_status_summary(conn))
    elif intent == "my_data":
        say(text=intake.my_data(conn, user_id, text))
    elif intent == "faq":
        if set_status:
            set_status("searching the workspace…")
        say(text=faq.answer(client, text, action_token))
    else:
        say(text=("I can *fill shifts*, *sign up volunteers*, *report coverage*, and *answer "
                  "logistics questions*. What do you need?"))


# ---------- Agent surfaces ----------

@assistant.thread_started
def on_thread_started(say: Say, set_suggested_prompts: SetSuggestedPrompts):
    say(text=WELCOME)
    set_suggested_prompts(prompts=SUGGESTED)


@assistant.user_message
def on_user_message(payload: dict, say: Say, set_status: SetStatus, client, context):
    conn = db.connect()
    if db.seen_event(conn, payload.get("client_msg_id") or payload.get("ts", "")):
        return
    _route_and_handle(client, conn, payload.get("text", ""), payload["user"], say,
                      set_status=set_status,
                      action_token=payload.get("assistant_thread", {}).get("action_token"))


app.assistant(assistant)


@app.event("app_mention")
def on_mention(event, say, client):
    conn = db.connect()
    if db.seen_event(conn, event.get("client_msg_id") or event.get("ts", "")):
        return
    text = re.sub(r"<@[^>]+>", "", event.get("text", "")).strip()
    _route_and_handle(client, conn, text, event["user"],
                      lambda **kw: say(thread_ts=event.get("thread_ts") or event["ts"], **kw),
                      channel_id=event["channel"],
                      thread_ts=event.get("thread_ts") or event["ts"],
                      action_token=event.get("action_token"))


@app.event("message")
def on_dm(event, say, client):
    """Plain DMs (messages tab) outside assistant threads."""
    if event.get("channel_type") != "im" or event.get("bot_id") or event.get("subtype"):
        return
    if event.get("assistant_thread") or event.get("thread_ts"):
        return  # assistant middleware owns those
    conn = db.connect()
    if db.seen_event(conn, event.get("client_msg_id") or event.get("ts", "")):
        return
    _route_and_handle(client, conn, event.get("text", ""), event["user"], say)


# ---------- Buttons ----------

def _volunteer_by_slack_id(conn, user_id: str):
    row = conn.execute("SELECT * FROM volunteers WHERE slack_user_id = ?", (user_id,)).fetchone()
    return db.row_to_volunteer(row) if row else None


@app.action("accept_shift")
def on_accept(ack, body, client, respond):
    ack()
    conn = db.connect()
    shift_id = int(body["actions"][0]["value"])
    v = _volunteer_by_slack_id(conn, body["user"]["id"])
    if not v:
        respond(text="I couldn't find you on the roster — say \"I'd like to volunteer\" first!")
        return
    status = outreach.record_response(conn, shift_id, v["id"], accept=True)
    shift = outreach.get_shift(conn, shift_id)
    if status == "accepted":
        respond(text=f"You're confirmed for *{shift['title']}*", blocks=blocks.accepted_blocks(shift))
    else:
        respond(text=f":raised_hands: *{shift['title']}* is already full — I've put you first on "
                     "the waitlist and I'll confirm you instantly if a spot opens.")
    outreach.check_fill(client, conn, shift_id)
    canvas.upsert(client, conn, outreach.get_shift(conn, shift_id))


@app.action("decline_shift")
def on_decline(ack, body, client, respond):
    ack()
    conn = db.connect()
    shift_id = int(body["actions"][0]["value"])
    v = _volunteer_by_slack_id(conn, body["user"]["id"])
    if v:
        outreach.record_response(conn, shift_id, v["id"], accept=False)
        outreach.check_fill(client, conn, shift_id)
    respond(text="No problem — thanks for letting me know quickly! :green_heart:")


@app.action("cancel_attendance")
def on_cancel(ack, body, client, respond):
    ack()
    conn = db.connect()
    shift_id = int(body["actions"][0]["value"])
    v = _volunteer_by_slack_id(conn, body["user"]["id"])
    if v:
        respond(text="Got it — thanks for the heads-up. Finding cover now; you're all set. :green_heart:")
        outreach.rescue(client, conn, shift_id, v["id"])
        canvas.upsert(client, conn, outreach.get_shift(conn, shift_id))


@app.action("pause_volunteering")
def on_pause(ack, body, respond):
    ack()
    conn = db.connect()
    respond(text=intake.my_data(conn, body["user"]["id"], "pause my volunteering"))


@app.action("confirm_intake")
def on_confirm_intake(ack, body, client, respond):
    ack()
    conn = db.connect()
    name = intake.confirm(client, conn, body["user"]["id"])
    respond(text=f":tada: Welcome to the roster, {name.split()[0]}! I'll reach out when a shift "
                 "matches your availability. You can update anytime by telling me what changed.")


@app.action("restart_intake")
def on_restart_intake(ack, body, respond):
    ack()
    conn = db.connect()
    intake.save_session(conn, body["user"]["id"], {})
    respond(text="Fresh start — tell me about your availability and any skills (driving, languages, first aid…).")


@app.action(re.compile(r"negotiate_\d"))
def on_negotiate(ack, body, client, respond):
    ack()
    conn = db.connect()
    shift_id_s, action = body["actions"][0]["value"].split(":", 1)
    note = negotiate.apply(client, conn, int(shift_id_s), action)
    respond(text=f":handshake: {note}")


@app.event("app_home_opened")
def on_home(event, client):
    conn = db.connect()
    client.views_publish(user_id=event["user"], view={
        "type": "home",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "Rally — volunteer HQ"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": _status_summary(conn)}},
            {"type": "context", "elements": [{"type": "mrkdwn",
                "text": "DM me to fill a shift, join the roster, or ask a question."}]},
        ],
    })


def _seed_roster_if_empty() -> None:
    """On ephemeral hosts (Fly/Railway) the DB may reset on redeploy. The demo roster is
    deterministic seed data, so recreate it if the volunteers table is empty."""
    conn = db.connect()
    if conn.execute("SELECT COUNT(*) c FROM volunteers").fetchone()["c"] == 0:
        from seeds import seed_roster
        seed_roster.main()


def main() -> None:
    missing = config.missing_required()
    if missing:
        # Fail fast with ONE clear line (not a traceback loop) so host logs are diagnostic.
        # The sleep avoids a tight restart loop that burns free-tier credits.
        print("FATAL: missing required environment variables: " + ", ".join(missing))
        print("Set these in your host's Variables/Secrets (exact names, no quotes), then redeploy.")
        time.sleep(30)
        raise SystemExit(1)
    db.connect()  # apply schema
    _seed_roster_if_empty()
    scheduler.start(app.client)
    print("Rally is running (Socket Mode)")
    SocketModeHandler(app, config.SLACK_APP_TOKEN).start()


if __name__ == "__main__":
    main()
