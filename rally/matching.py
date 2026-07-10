"""Matching engine. Pure functions over the roster — no LLM calls (efficiency by design).

Fairness: candidates ordered least-recently-asked, with a monthly ask cap, so the same
eager volunteers aren't burned out (volunteer churn is the sector's core problem).
"""
import math
from datetime import datetime

from rally import config, db

TIME_BUCKETS = [(5, 12, "morning"), (12, 17, "afternoon"), (17, 23, "evening")]


def availability_tag(starts_at: str) -> str:
    """'2026-07-12T09:00' -> 'weekend_morning'"""
    dt = datetime.fromisoformat(starts_at)
    day = "weekend" if dt.weekday() >= 5 else "weekday"
    bucket = "morning"
    for lo, hi, name in TIME_BUCKETS:
        if lo <= dt.hour < hi:
            bucket = name
            break
    return f"{day}_{bucket}"


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return a_start < b_end and b_start < a_end


def _conflicting_volunteer_ids(conn, shift: dict) -> set[int]:
    rows = conn.execute(
        """SELECT a.volunteer_id, s.starts_at, s.ends_at FROM assignments a
           JOIN shifts s ON s.id = a.shift_id
           WHERE a.status IN ('invited', 'accepted') AND s.status IN ('open', 'filled')
             AND s.id != ?""",
        (shift["id"],),
    ).fetchall()
    return {
        r["volunteer_id"]
        for r in rows
        if overlaps(shift["starts_at"], shift["ends_at"], r["starts_at"], r["ends_at"])
    }


def eligible_volunteers(conn, shift: dict) -> list[dict]:
    """Active, availability window matches, no time conflict, under the monthly ask cap.
    Ordered least-recently-asked (fairness)."""
    tag = availability_tag(shift["starts_at"])
    conflicts = _conflicting_volunteer_ids(conn, shift)
    already = {
        r["volunteer_id"]
        for r in conn.execute(
            "SELECT volunteer_id FROM assignments WHERE shift_id = ?", (shift["id"],)
        )
    }
    rows = conn.execute(
        "SELECT * FROM volunteers WHERE active = 1 AND asks_this_month < ? "
        "ORDER BY COALESCE(last_asked_at, '') ASC",
        (config.MAX_ASKS_PER_MONTH,),
    ).fetchall()
    out = []
    for r in rows:
        v = db.row_to_volunteer(r)
        if v["id"] in conflicts or v["id"] in already:
            continue
        if tag not in v["availability"]:
            continue
        out.append(v)
    return out


def _holders(pool: list[dict], kind: str, value: str) -> list[dict]:
    return [v for v in pool if value in v[kind]]


def plan_invites(conn, shift: dict) -> dict:
    """Greedy plan: satisfy scarce requirements first, then general slots, then a decline
    buffer. Returns {'invite': [volunteers], 'feasible': bool, 'shortfalls': [...]}
    Shortfalls feed the negotiation flow (RALLY-REVIEW.md R2)."""
    pool = eligible_volunteers(conn, shift)
    reqs = shift.get("requirements") or {}
    invite: list[dict] = []
    invited_ids: set[int] = set()
    shortfalls: list[dict] = []

    def take(candidates: list[dict], count: int) -> int:
        taken = 0
        for v in candidates:
            if taken >= count:
                break
            if v["id"] not in invited_ids:
                invite.append(v)
                invited_ids.add(v["id"])
                taken += 1
        return taken

    # 1. Scarce requirements first (certs, then langs), scarcest requirement first.
    req_items = [(k, val, n) for k in ("certs", "langs") for val, n in (reqs.get(k) or {}).items()]
    req_items.sort(key=lambda item: len(_holders(pool, item[0], item[1])))
    for kind, value, needed_count in req_items:
        holders = _holders(pool, kind, value)
        got = take(holders, needed_count)
        if got < needed_count:
            shortfalls.append(
                {"kind": kind, "value": value, "needed": needed_count, "available": got}
            )

    # 2. Fill remaining general slots plus a decline buffer.
    target = min(
        max(shift["needed"], len(invite)),
        math.ceil(shift["needed"] * config.OVER_INVITE_FACTOR),
    )
    take([v for v in pool if v["id"] not in invited_ids], target - len(invite))

    total_possible = len(pool)
    if total_possible < shift["needed"]:
        shortfalls.append(
            {"kind": "headcount", "value": "total", "needed": shift["needed"],
             "available": total_possible}
        )
    return {"invite": invite, "feasible": not shortfalls, "shortfalls": shortfalls}


def shift_progress(conn, shift_id: int) -> dict:
    """Live tallies for the status card and fill checks."""
    rows = conn.execute(
        """SELECT a.status, v.name, v.certs, v.langs, v.is_simulated FROM assignments a
           JOIN volunteers v ON v.id = a.volunteer_id WHERE a.shift_id = ?""",
        (shift_id,),
    ).fetchall()
    by_status: dict[str, list[dict]] = {}
    for r in rows:
        by_status.setdefault(r["status"], []).append(
            {"name": r["name"], "is_simulated": bool(r["is_simulated"])}
        )
    return {
        "accepted": by_status.get("accepted", []),
        "invited": by_status.get("invited", []),
        "declined": by_status.get("declined", []),
        "cancelled": by_status.get("cancelled", []),
    }
