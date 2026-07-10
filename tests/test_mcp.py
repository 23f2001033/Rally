"""Test the MCP server tools via FastMCP's in-memory client — proves the Claude Desktop
demo beat works without needing Claude Desktop. Seeds a finished-shift scenario so the
impact tools have data."""
import asyncio
import json

from fastmcp import Client

from rally import db, mcp_server


def _seed_impact(conn):
    """One filled shift + logged hours, so impact_summary/get_shift_status show real data."""
    conn.execute("DELETE FROM hours_ledger")
    conn.execute("DELETE FROM assignments")
    conn.execute("DELETE FROM shifts")
    cur = conn.execute(
        """INSERT INTO shifts (title, starts_at, ends_at, location, needed, requirements,
           status, coordinator_id, created_at) VALUES
           ('Saturday food drive','2026-07-11T09:00','2026-07-11T13:00','Warehouse',6,'{}',
            'filled','UCOORD',?)""", (db.now_iso(),))
    shift_id = cur.lastrowid
    vols = conn.execute("SELECT id FROM volunteers LIMIT 6").fetchall()
    for r in vols:
        conn.execute("INSERT INTO assignments (shift_id, volunteer_id, status, invited_at) "
                     "VALUES (?, ?, 'accepted', ?)", (shift_id, r["id"], db.now_iso()))
        conn.execute("INSERT INTO hours_ledger (volunteer_id, shift_id, hours, logged_at) "
                     "VALUES (?, ?, 4.0, ?)", (r["id"], shift_id, db.now_iso()))
    conn.commit()


def test_mcp_tools():
    conn = db.connect()
    _seed_impact(conn)

    async def run():
        async with Client(mcp_server.mcp) as client:
            tools = {t.name for t in await client.list_tools()}
            assert {"find_volunteers", "get_shift_status", "log_hours", "impact_summary"} <= tools, tools

            drivers = json.loads((await client.call_tool(
                "find_volunteers", {"cert": "driver"})).content[0].text)
            assert drivers["count"] > 0 and all("driver" in v["certs"] for v in drivers["volunteers"])

            status = json.loads((await client.call_tool("get_shift_status", {})).content[0].text)
            assert status["shifts"] and status["shifts"][0]["status"] == "filled"
            assert len(status["shifts"][0]["confirmed"]) == 6

            impact = json.loads((await client.call_tool("impact_summary", {})).content[0].text)
            assert impact["total_hours"] == 24.0, impact
            assert impact["shifts_fully_staffed"] >= 1
            return drivers["count"], impact["total_hours"]

    driver_count, hours = asyncio.run(run())
    print(f"\nMCP OK: {driver_count} drivers findable, {hours}h impact total")


if __name__ == "__main__":
    test_mcp_tools()
