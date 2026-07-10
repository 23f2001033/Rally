"""Outreach + fill tracking: the agentic loop's hands.

Invite DMs are templates (zero LLM cost). Simulated volunteers get their 'DM' recorded
and a delayed sim_response job instead of a real message (RALLY-REVIEW.md R1).
"""
import json
import random
from datetime import datetime, timedelta, timezone

from rally import blocks, config, db, matching


def _iso_in(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def create_shift(conn, parsed: dict, coordinator_id: str, channel_id: str | None,
                 thread_ts: str | None) -> dict:
    cur = conn.execute(
        """INSERT INTO shifts (title, starts_at, ends_at, location, needed, requirements,
                               coordinator_id, channel_id, thread_ts, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed["title"], parsed["starts_at"], parsed["ends_at"], parsed.get("location", ""),
         int(parsed["needed"]), json.dumps(parsed.get("requirements") or {}),
         coordinator_id, channel_id, thread_ts, db.now_iso()),
    )
    conn.commit()
    return db.row_to_shift(
        conn.execute("SELECT * FROM shifts WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


def get_shift(conn, shift_id: int) -> dict:
    return db.row_to_shift(
        conn.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,)).fetchone()
    )


def send_invites(client, conn, shift: dict, volunteers: list[dict]) -> int:
    sent = 0
    for v in volunteers:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO assignments (shift_id, volunteer_id, status, invited_at)"
                " VALUES (?, ?, 'invited', ?)",
                (shift["id"], v["id"], db.now_iso()),
            )
            if conn.execute("SELECT changes()").fetchone()[0] == 0:
                continue  # idempotency: already invited to this shift
            conn.execute(
                "UPDATE volunteers SET last_asked_at = ?, asks_this_month = asks_this_month + 1"
                " WHERE id = ?", (db.now_iso(), v["id"]),
            )
            conn.commit()
            if v["is_simulated"]:
                delay = random.randint(*config.SIM_RESPONSE_DELAY_RANGE)
                db.add_job(conn, "sim_response", _iso_in(delay),
                           {"shift_id": shift["id"], "volunteer_id": v["id"]})
            else:
                resp = client.chat_postMessage(
                    channel=v["slack_user_id"],
                    text=f"Can you help with {shift['title']}?",
                    blocks=blocks.invite_blocks(shift, v),
                )
                conn.execute(
                    "UPDATE assignments SET invite_channel = ?, invite_ts = ?"
                    " WHERE shift_id = ? AND volunteer_id = ?",
                    (resp["channel"], resp["ts"], shift["id"], v["id"]),
                )
                conn.commit()
            sent += 1
        except Exception as e:  # one bad DM must not sink the wave
            print(f"[outreach] invite failed for {v['name']}: {e}")
    return sent


def post_or_update_status_card(client, conn, shift: dict) -> None:
    progress = matching.shift_progress(conn, shift["id"])
    card = blocks.status_card_blocks(shift, progress)
    if shift.get("status_card_ts"):
        client.chat_update(channel=shift["status_card_channel"], ts=shift["status_card_ts"],
                           text=f"Status: {shift['title']}", blocks=card)
    else:
        target = shift.get("channel_id") or shift["coordinator_id"]
        kwargs = {"channel": target, "text": f"Status: {shift['title']}", "blocks": card}
        if shift.get("thread_ts"):
            kwargs["thread_ts"] = shift["thread_ts"]
        resp = client.chat_postMessage(**kwargs)
        conn.execute("UPDATE shifts SET status_card_channel = ?, status_card_ts = ? WHERE id = ?",
                     (resp["channel"], resp["ts"], shift["id"]))
        conn.commit()


def record_response(conn, shift_id: int, volunteer_id: int, accept: bool) -> str:
    """Returns resulting assignment status. Guards against over-filling (first-accept-wins)."""
    shift = get_shift(conn, shift_id)
    progress = matching.shift_progress(conn, shift_id)
    if accept and len(progress["accepted"]) >= shift["needed"]:
        status = "waitlisted"
    else:
        status = "accepted" if accept else "declined"
    conn.execute(
        "UPDATE assignments SET status = ?, responded_at = ? WHERE shift_id = ? AND volunteer_id = ?",
        (status, db.now_iso(), shift_id, volunteer_id),
    )
    conn.commit()
    return status


def check_fill(client, conn, shift_id: int) -> None:
    """Goal loop: filled -> celebrate + log hours plan; short + pool remains -> next wave;
    short + pool exhausted -> negotiate with coordinator."""
    from rally import negotiate  # local import to avoid cycle

    shift = get_shift(conn, shift_id)
    if shift["status"] not in ("open",):
        return
    progress = matching.shift_progress(conn, shift_id)
    accepted = len(progress["accepted"])

    if accepted >= shift["needed"]:
        conn.execute("UPDATE shifts SET status = 'filled' WHERE id = ?", (shift_id,))
        conn.commit()
        shift["status"] = "filled"
        post_or_update_status_card(client, conn, shift)
        client.chat_postMessage(
            channel=shift["status_card_channel"] or shift["coordinator_id"],
            thread_ts=shift.get("status_card_ts"),
            text=f":tada: *{shift['title']}* is fully staffed ({accepted}/{shift['needed']}). "
                 "I'll watch for cancellations and re-fill automatically.",
        )
        return

    post_or_update_status_card(client, conn, shift)
    if not progress["invited"]:  # everyone answered and we're still short
        plan = matching.plan_invites(conn, shift)
        if plan["invite"]:
            send_invites(client, conn, shift, plan["invite"])
            db.add_job(conn, "fill_check", _iso_in(45), {"shift_id": shift_id})
        else:
            negotiate.propose(client, conn, shift, plan["shortfalls"])


def rescue(client, conn, shift_id: int, volunteer_id: int) -> None:
    """Dropout rescue: mark cancelled, promote waitlist or invite next-best, notify coordinator."""
    conn.execute(
        "UPDATE assignments SET status = 'cancelled', responded_at = ? "
        "WHERE shift_id = ? AND volunteer_id = ?",
        (db.now_iso(), shift_id, volunteer_id),
    )
    conn.execute("UPDATE shifts SET status = 'open' WHERE id = ? AND status = 'filled'", (shift_id,))
    conn.commit()
    shift = get_shift(conn, shift_id)

    promoted = conn.execute(
        "SELECT a.volunteer_id, v.name, v.slack_user_id, v.is_simulated FROM assignments a "
        "JOIN volunteers v ON v.id = a.volunteer_id "
        "WHERE a.shift_id = ? AND a.status = 'waitlisted' ORDER BY a.responded_at LIMIT 1",
        (shift_id,),
    ).fetchone()
    dropout = conn.execute("SELECT name FROM volunteers WHERE id = ?", (volunteer_id,)).fetchone()

    if promoted:
        conn.execute("UPDATE assignments SET status = 'accepted' WHERE shift_id = ? AND volunteer_id = ?",
                     (shift_id, promoted["volunteer_id"]))
        conn.commit()
        if not promoted["is_simulated"]:
            client.chat_postMessage(
                channel=promoted["slack_user_id"],
                text=f":tada: A spot opened up — you're now confirmed for *{shift['title']}*!",
                blocks=blocks.accepted_blocks(shift),
            )
        note = f"{dropout['name']} had to drop *{shift['title']}* — I promoted {promoted['name']} from the waitlist. All set."
    else:
        plan = matching.plan_invites(conn, shift)
        wave = plan["invite"][: max(1, shift["needed"])]
        if wave:
            send_invites(client, conn, shift, wave)
            db.add_job(conn, "fill_check", _iso_in(45), {"shift_id": shift_id})
            note = (f"{dropout['name']} had to drop *{shift['title']}* — already reaching out to "
                    f"{len(wave)} replacement{'s' if len(wave) != 1 else ''}. I'll confirm shortly.")
        else:
            note = (f":warning: {dropout['name']} dropped *{shift['title']}* and I'm out of eligible "
                    "volunteers — see options below.")
            from rally import negotiate
            negotiate.propose(client, conn, shift, plan["shortfalls"])
    client.chat_postMessage(channel=shift["coordinator_id"], text=note)
    post_or_update_status_card(client, conn, shift)
