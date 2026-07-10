"""Offline tests for the matching engine + fill/rescue state machine (no Slack, no LLM)."""
import json

import pytest

from rally import config, db, matching, outreach


@pytest.fixture()
def conn(tmp_path):
    return db.connect(str(tmp_path / "test.db"))


def add_volunteer(conn, name, certs=(), langs=(), availability=("weekend_morning",),
                  last_asked=None, sim=1, active=1):
    cur = conn.execute(
        """INSERT INTO volunteers (slack_user_id, name, skills, certs, langs, availability,
           active, is_simulated, last_asked_at, created_at)
           VALUES (?, ?, '[]', ?, ?, ?, ?, ?, ?, ?)""",
        (f"U{name}", name, json.dumps(list(certs)), json.dumps(list(langs)),
         json.dumps(list(availability)), active, sim, last_asked, db.now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def make_shift(conn, needed=4, requirements=None, starts="2026-07-11T09:00", ends="2026-07-11T13:00"):
    return outreach.create_shift(conn, {
        "title": "Test shift", "starts_at": starts, "ends_at": ends,
        "needed": needed, "requirements": requirements or {}, "location": "Warehouse",
    }, coordinator_id="UCOORD", channel_id=None, thread_ts=None)


def test_availability_tag():
    assert matching.availability_tag("2026-07-11T09:00") == "weekend_morning"   # Saturday
    assert matching.availability_tag("2026-07-13T18:30") == "weekday_evening"   # Monday


def test_requirements_prioritized(conn):
    add_volunteer(conn, "DriverA", certs=["driver"])
    add_volunteer(conn, "DriverB", certs=["driver"])
    for i in range(6):
        add_volunteer(conn, f"Plain{i}")
    shift = make_shift(conn, needed=4, requirements={"certs": {"driver": 2}})
    plan = matching.plan_invites(conn, shift)
    names = [v["name"] for v in plan["invite"]]
    assert "DriverA" in names and "DriverB" in names
    assert plan["feasible"]


def test_shortfall_reported(conn):
    add_volunteer(conn, "OnlyDriver", certs=["driver"])
    add_volunteer(conn, "Plain0")
    shift = make_shift(conn, needed=2, requirements={"certs": {"driver": 2}})
    plan = matching.plan_invites(conn, shift)
    assert not plan["feasible"]
    assert any(s["kind"] == "certs" and s["value"] == "driver" for s in plan["shortfalls"])


def test_availability_filter(conn):
    add_volunteer(conn, "WeekdayOnly", availability=["weekday_morning"])
    add_volunteer(conn, "Weekender", availability=["weekend_morning"])
    shift = make_shift(conn)  # Saturday morning
    names = [v["name"] for v in matching.eligible_volunteers(conn, shift)]
    assert names == ["Weekender"]


def test_conflict_exclusion(conn):
    vid = add_volunteer(conn, "Busy")
    add_volunteer(conn, "Free")
    s1 = make_shift(conn, needed=1)
    conn.execute(
        "INSERT INTO assignments (shift_id, volunteer_id, status, invited_at) VALUES (?, ?, 'accepted', ?)",
        (s1["id"], vid, db.now_iso()))
    conn.commit()
    s2 = make_shift(conn, needed=1, starts="2026-07-11T10:00", ends="2026-07-11T12:00")  # overlaps
    names = [v["name"] for v in matching.eligible_volunteers(conn, s2)]
    assert "Busy" not in names and "Free" in names


def test_fairness_least_recently_asked(conn):
    add_volunteer(conn, "AskedYesterday", last_asked="2026-07-09T00:00:00+00:00")
    add_volunteer(conn, "NeverAsked", last_asked=None)
    shift = make_shift(conn, needed=1)
    plan = matching.plan_invites(conn, shift)
    assert plan["invite"][0]["name"] == "NeverAsked"


def test_ask_cap(conn):
    vid = add_volunteer(conn, "Overasked")
    conn.execute("UPDATE volunteers SET asks_this_month = ? WHERE id = ?",
                 (config.MAX_ASKS_PER_MONTH, vid))
    conn.commit()
    shift = make_shift(conn, needed=1)
    assert matching.eligible_volunteers(conn, shift) == []


def test_accept_then_overfill_waitlists(conn):
    v1 = add_volunteer(conn, "First")
    v2 = add_volunteer(conn, "Second")
    shift = make_shift(conn, needed=1)
    for vid in (v1, v2):
        conn.execute(
            "INSERT INTO assignments (shift_id, volunteer_id, status, invited_at) VALUES (?, ?, 'invited', ?)",
            (shift["id"], vid, db.now_iso()))
    conn.commit()
    assert outreach.record_response(conn, shift["id"], v1, accept=True) == "accepted"
    assert outreach.record_response(conn, shift["id"], v2, accept=True) == "waitlisted"


def test_normalize_state_shapes():
    from rally import intake
    # nested dict form
    assert intake.normalize_state({"certs": {"driver": True, "forklift": False}})["certs"] == ["driver"]
    # bare string form
    assert intake.normalize_state({"langs": "es"})["langs"] == ["es"]
    # stray top-level known tag (the live failure mode)
    n = intake.normalize_state({"availability": ["weekend_morning"], "driver": True})
    assert n["certs"] == ["driver"] and n["availability"] == ["weekend_morning"]
    # list form passthrough + dedupe
    assert intake.normalize_state({"skills": ["cooking", "cooking"]})["skills"] == ["cooking"]
    # empty
    assert intake.normalize_state({})== {"availability": [], "certs": [], "langs": [], "skills": []}


def test_invite_idempotency(conn, monkeypatch):
    class FakeClient:
        def chat_postMessage(self, **kw):
            raise AssertionError("simulated volunteers must not get real DMs")
    v = add_volunteer(conn, "Sim", sim=1)
    shift = make_shift(conn, needed=1)
    vol = db.row_to_volunteer(conn.execute("SELECT * FROM volunteers WHERE id = ?", (v,)).fetchone())
    assert outreach.send_invites(FakeClient(), conn, shift, [vol]) == 1
    assert outreach.send_invites(FakeClient(), conn, shift, [vol]) == 0  # second wave: no dup
    jobs = conn.execute("SELECT COUNT(*) c FROM jobs WHERE kind='sim_response'").fetchone()["c"]
    assert jobs == 1
