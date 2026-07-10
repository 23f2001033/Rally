"""Rally MCP server (qualifying technology): the volunteer roster, shift coverage, and
impact ledger, queryable from any MCP client (Claude Desktop, Cursor...).

Run (stdio, for Claude Desktop):  python -m rally.mcp_server
"""
import json

from fastmcp import FastMCP

from rally import db, matching

mcp = FastMCP(
    "Rally",
    instructions="Volunteer coordination data for a nonprofit's Slack workspace: search the "
                 "roster, check shift coverage, and summarize volunteer impact hours.",
)


@mcp.tool()
def find_volunteers(cert: str = "", lang: str = "", availability: str = "") -> str:
    """Search the volunteer roster. Filters (all optional): cert (driver, first_aid,
    food_safety, forklift), lang (es, hi, zh, fr), availability (e.g. weekend_morning)."""
    conn = db.connect()
    rows = conn.execute("SELECT * FROM volunteers WHERE active = 1").fetchall()
    out = []
    for r in rows:
        v = db.row_to_volunteer(r)
        if cert and cert not in v["certs"]:
            continue
        if lang and lang not in v["langs"]:
            continue
        if availability and availability not in v["availability"]:
            continue
        out.append({"name": v["name"], "certs": v["certs"], "langs": v["langs"],
                    "availability": v["availability"], "simulated": bool(v["is_simulated"])})
    return json.dumps({"count": len(out), "volunteers": out[:25]}, indent=1)


@mcp.tool()
def get_shift_status(shift_title: str = "") -> str:
    """Coverage for upcoming shifts. Optionally filter by (partial) shift title."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM shifts WHERE status IN ('open','filled') ORDER BY starts_at"
    ).fetchall()
    out = []
    for r in rows:
        s = db.row_to_shift(r)
        if shift_title and shift_title.lower() not in s["title"].lower():
            continue
        p = matching.shift_progress(conn, s["id"])
        out.append({
            "title": s["title"], "starts_at": s["starts_at"], "needed": s["needed"],
            "status": s["status"],
            "confirmed": [x["name"] for x in p["accepted"]],
            "awaiting_reply": len(p["invited"]),
            "requirements": s["requirements"],
        })
    return json.dumps({"shifts": out}, indent=1)


@mcp.tool()
def log_hours(volunteer_name: str, shift_title: str, hours: float) -> str:
    """Log contributed hours for a volunteer against a shift (coordinator use)."""
    conn = db.connect()
    v = conn.execute("SELECT id FROM volunteers WHERE name LIKE ?", (f"%{volunteer_name}%",)).fetchone()
    s = conn.execute("SELECT id FROM shifts WHERE title LIKE ?", (f"%{shift_title}%",)).fetchone()
    if not v or not s:
        return json.dumps({"error": "volunteer or shift not found"})
    conn.execute("INSERT INTO hours_ledger (volunteer_id, shift_id, hours, logged_at) VALUES (?, ?, ?, ?)",
                 (v["id"], s["id"], hours, db.now_iso()))
    conn.commit()
    return json.dumps({"ok": True})


@mcp.tool()
def impact_summary() -> str:
    """Grant-ready impact summary: total volunteer hours, per-volunteer totals, shifts staffed."""
    conn = db.connect()
    total = conn.execute("SELECT COALESCE(SUM(hours),0) h FROM hours_ledger").fetchone()["h"]
    per = conn.execute(
        """SELECT v.name, SUM(l.hours) h FROM hours_ledger l JOIN volunteers v ON v.id = l.volunteer_id
           GROUP BY v.id ORDER BY h DESC LIMIT 20"""
    ).fetchall()
    staffed = conn.execute("SELECT COUNT(*) c FROM shifts WHERE status IN ('filled','done')").fetchone()["c"]
    return json.dumps({
        "total_hours": total, "shifts_fully_staffed": staffed,
        "top_volunteers": [{"name": r["name"], "hours": r["h"]} for r in per],
    }, indent=1)


if __name__ == "__main__":
    mcp.run()
