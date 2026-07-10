"""Offline end-to-end: the full fill/rescue loop with simulated volunteers and a fake
Slack client. No network, no LLM — proves the agentic state machine before Slack exists."""
import json

import pytest

from rally import config, db, matching, outreach, scheduler


class FakeClient:
    def __init__(self):
        self.messages = []
        self._ts = 0

    def chat_postMessage(self, **kw):
        self._ts += 1
        self.messages.append(kw)
        return {"channel": kw.get("channel", "C1"), "ts": f"{self._ts}.000"}

    def chat_update(self, **kw):
        self.messages.append(kw)
        return {"ok": True}


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SIM_RESPONSE_DELAY_RANGE", (0, 0))  # respond immediately
    c = db.connect(str(tmp_path / "e2e.db"))
    for i in range(14):
        certs = ["driver"] if i < 4 else []
        c.execute(
            """INSERT INTO volunteers (slack_user_id, name, skills, certs, langs, availability,
               active, is_simulated, created_at) VALUES (?, ?, '[]', ?, '[]', ?, 1, 1, ?)""",
            (f"SIM-{i}", f"Vol{i}", json.dumps(certs),
             json.dumps(["weekend_morning"]), db.now_iso()),
        )
    c.commit()
    return c


def drain_jobs(client, conn, max_rounds=30):
    for _ in range(max_rounds):
        jobs = db.due_jobs(conn)
        if not jobs:
            return
        for job in jobs:
            db.finish_job(conn, job["id"])
            scheduler._handle(client, conn, job)


def test_fill_loop_reaches_filled(conn):
    client = FakeClient()
    shift = outreach.create_shift(conn, {
        "title": "Saturday food drive", "starts_at": "2026-07-11T09:00",
        "ends_at": "2026-07-11T13:00", "needed": 4,
        "requirements": {"certs": {"driver": 2}}, "location": "Warehouse",
    }, "UCOORD", None, None)
    plan = matching.plan_invites(conn, shift)
    assert plan["feasible"]
    outreach.send_invites(client, conn, shift, plan["invite"])
    outreach.post_or_update_status_card(client, conn, outreach.get_shift(conn, shift["id"]))

    drain_jobs(client, conn)

    final = outreach.get_shift(conn, shift["id"])
    progress = matching.shift_progress(conn, shift["id"])
    assert final["status"] == "filled", f"progress: { {k: len(v) for k, v in progress.items()} }"
    assert len(progress["accepted"]) == 4
    # drivers requirement honored in outreach set
    invited_all = conn.execute(
        """SELECT v.certs FROM assignments a JOIN volunteers v ON v.id=a.volunteer_id
           WHERE a.shift_id=? AND a.status='accepted'""", (shift["id"],)).fetchall()
    assert sum(1 for r in invited_all if "driver" in r["certs"]) >= 1


def test_rescue_refills_after_cancellation(conn):
    client = FakeClient()
    shift = outreach.create_shift(conn, {
        "title": "Sorting shift", "starts_at": "2026-07-11T09:00",
        "ends_at": "2026-07-11T13:00", "needed": 3, "requirements": {}, "location": "",
    }, "UCOORD", None, None)
    outreach.send_invites(client, conn, shift, matching.plan_invites(conn, shift)["invite"])
    outreach.post_or_update_status_card(client, conn, outreach.get_shift(conn, shift["id"]))
    drain_jobs(client, conn)
    assert outreach.get_shift(conn, shift["id"])["status"] == "filled"

    dropout = conn.execute(
        "SELECT volunteer_id FROM assignments WHERE shift_id=? AND status='accepted' LIMIT 1",
        (shift["id"],)).fetchone()["volunteer_id"]
    outreach.rescue(client, conn, shift["id"], dropout)
    drain_jobs(client, conn)

    progress = matching.shift_progress(conn, shift["id"])
    assert len(progress["accepted"]) == 3, "rescue must restore full staffing"
    assert outreach.get_shift(conn, shift["id"])["status"] == "filled"
    cancelled = conn.execute(
        "SELECT COUNT(*) c FROM assignments WHERE shift_id=? AND status='cancelled'",
        (shift["id"],)).fetchone()["c"]
    assert cancelled == 1
