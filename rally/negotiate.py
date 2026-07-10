"""Constraint negotiation (RALLY-REVIEW.md R2): when a shift can't be filled as specified,
Rally reasons about trade-offs and proposes options instead of failing silently."""
import json

from rally import blocks, db, llm, matching


def propose(client, conn, shift: dict, shortfalls: list[dict]) -> None:
    pool = matching.eligible_volunteers(conn, shift)
    try:
        result = llm.negotiate_options(shift, shortfalls, len(pool))
        summary, options = result["summary"], result["options"]
    except Exception:
        summary = "Not enough eligible volunteers match every requirement."
        options = [
            {"label": "Relax requirements", "description": "Fill remaining slots ignoring cert/language requirements.",
             "action": "relax_requirement", "params": {}},
            {"label": "Widen the pool", "description": "Also ask volunteers outside their usual availability window.",
             "action": "widen_pool", "params": {}},
        ]
    client.chat_postMessage(
        channel=shift["status_card_channel"] or shift["coordinator_id"],
        thread_ts=shift.get("status_card_ts"),
        text=f"{shift['title']}: can't fill as specified — options inside.",
        blocks=blocks.negotiation_blocks(shift, summary, options),
    )


def apply(client, conn, shift_id: int, action: str) -> str:
    """Coordinator picked an option. Mutate constraints, then resume the fill loop."""
    from rally import outreach

    shift = outreach.get_shift(conn, shift_id)
    if action == "relax_requirement":
        conn.execute("UPDATE shifts SET requirements = '{}' WHERE id = ?", (shift_id,))
        conn.commit()
        note = "Requirements relaxed — resuming outreach."
    elif action == "reduce_headcount":
        progress = matching.shift_progress(conn, shift_id)
        new_needed = max(len(progress["accepted"]), 1)
        conn.execute("UPDATE shifts SET needed = ? WHERE id = ?", (new_needed, shift_id))
        conn.commit()
        note = f"Headcount reduced to {new_needed}."
    elif action == "widen_pool":
        # Widen = ignore availability windows: implemented as a direct extra wave.
        shift = outreach.get_shift(conn, shift_id)
        already = {r["volunteer_id"] for r in conn.execute(
            "SELECT volunteer_id FROM assignments WHERE shift_id = ?", (shift_id,))}
        rows = conn.execute(
            "SELECT * FROM volunteers WHERE active = 1 ORDER BY COALESCE(last_asked_at,'')").fetchall()
        extra = [db.row_to_volunteer(r) for r in rows if r["id"] not in already][: shift["needed"] * 2]
        outreach.send_invites(client, conn, shift, extra)
        note = f"Widened the pool — asked {len(extra)} more volunteers outside their usual windows."
    else:  # open_call
        target = shift.get("channel_id") or shift["status_card_channel"] or shift["coordinator_id"]
        client.chat_postMessage(
            channel=target,
            text=(f":mega: *Open call!* We still need help with *{shift['title']}* "
                  f"({blocks.fmt_when(shift)}). DM me \"I can help with {shift['title']}\" to claim a spot!"),
        )
        note = "Posted an open call to the channel."
    shift = outreach.get_shift(conn, shift_id)
    outreach.check_fill(client, conn, shift_id)
    return note
