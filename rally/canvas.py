"""Event canvas: a live roster/logistics document per shift."""
from rally import blocks, matching


def _markdown(shift: dict, progress: dict) -> str:
    lines = [
        f"# {shift['title']}",
        f"**When:** {blocks.fmt_when(shift)}",
        f"**Where:** {shift.get('location') or 'TBA'}",
        f"**Coordinator:** <@{shift['coordinator_id']}>",
        "",
        f"## Confirmed volunteers ({len(progress['accepted'])}/{shift['needed']})",
    ]
    for p in progress["accepted"]:
        lines.append(f"- [ ] {p['name']}" + (" 🤖" if p["is_simulated"] else ""))
    lines += ["", "## Logistics", "- Park in the rear lot (see #logistics)",
              "- Check in with the coordinator on arrival",
              "", "_Maintained automatically by Rally._"]
    return "\n".join(lines)


def upsert(client, conn, shift: dict) -> str | None:
    progress = matching.shift_progress(conn, shift["id"])
    md = _markdown(shift, progress)
    try:
        if shift.get("canvas_id"):
            client.api_call("canvases.edit", json={
                "canvas_id": shift["canvas_id"],
                "changes": [{"operation": "replace", "document_content": {
                    "type": "markdown", "markdown": md}}],
            })
            return shift["canvas_id"]
        resp = client.api_call("canvases.create", json={
            "title": f"{shift['title']} — volunteer sheet",
            "document_content": {"type": "markdown", "markdown": md},
        })
        canvas_id = resp.get("canvas_id")
        if canvas_id:
            conn.execute("UPDATE shifts SET canvas_id = ? WHERE id = ?", (canvas_id, shift["id"]))
            conn.commit()
        return canvas_id
    except Exception as e:
        print(f"[canvas] upsert failed: {e}")
        return None
