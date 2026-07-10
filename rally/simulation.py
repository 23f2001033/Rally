"""Simulation mode (RALLY-REVIEW.md R1): seeded volunteer personas auto-respond so a solo
judge can experience the multi-party fill/rescue loop. Clearly labeled 🤖 everywhere.

Deterministic pseudo-randomness (volunteer_id, shift_id) keyed so demo runs are stable-ish
but varied across shifts."""
import hashlib

from rally import db, outreach

ACCEPT_RATE = 0.7


def _accepts(volunteer_id: int, shift_id: int) -> bool:
    h = hashlib.sha256(f"{volunteer_id}:{shift_id}".encode()).digest()
    return (h[0] / 255) < ACCEPT_RATE


def respond(client, conn, shift_id: int, volunteer_id: int) -> None:
    row = conn.execute(
        "SELECT status FROM assignments WHERE shift_id = ? AND volunteer_id = ?",
        (shift_id, volunteer_id),
    ).fetchone()
    if not row or row["status"] != "invited":
        return  # idempotent: already responded / rescinded
    outreach.record_response(conn, shift_id, volunteer_id, accept=_accepts(volunteer_id, shift_id))
    outreach.check_fill(client, conn, shift_id)


def cancel_random_accepted(client, conn, shift_id: int) -> str | None:
    """Demo helper: '@Rally simulate a cancellation' — a simulated confirmed volunteer drops,
    triggering the rescue loop live in front of the judge."""
    row = conn.execute(
        """SELECT a.volunteer_id, v.name FROM assignments a
           JOIN volunteers v ON v.id = a.volunteer_id
           WHERE a.shift_id = ? AND a.status = 'accepted' AND v.is_simulated = 1 LIMIT 1""",
        (shift_id,),
    ).fetchone()
    if not row:
        return None
    outreach.rescue(client, conn, shift_id, row["volunteer_id"])
    return row["name"]
