"""SQLite store. Volunteers, shifts, assignments, hours ledger, persisted jobs, event dedupe."""
import json
import sqlite3
import threading
from datetime import datetime, timezone

from rally import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS volunteers (
    id INTEGER PRIMARY KEY,
    slack_user_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    skills TEXT NOT NULL DEFAULT '[]',        -- json list of tags
    certs TEXT NOT NULL DEFAULT '[]',         -- json list: driver, first_aid, food_safety...
    langs TEXT NOT NULL DEFAULT '[]',         -- json list: es, hi, zh...
    availability TEXT NOT NULL DEFAULT '[]',  -- json list: weekday_morning, weekend_afternoon...
    active INTEGER NOT NULL DEFAULT 1,        -- 0 = paused ("pause my volunteering")
    is_simulated INTEGER NOT NULL DEFAULT 0,
    last_asked_at TEXT,                       -- ISO; fairness ordering (least recently asked)
    asks_this_month INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,                  -- ISO local, e.g. 2026-07-12T09:00
    ends_at TEXT NOT NULL,
    location TEXT DEFAULT '',
    needed INTEGER NOT NULL,
    requirements TEXT NOT NULL DEFAULT '{}',  -- json: {"certs":{"driver":2},"langs":{"es":1}}
    status TEXT NOT NULL DEFAULT 'open',      -- open | filled | cancelled | done
    coordinator_id TEXT NOT NULL,
    channel_id TEXT,
    thread_ts TEXT,
    status_card_channel TEXT,
    status_card_ts TEXT,
    canvas_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY,
    shift_id INTEGER NOT NULL REFERENCES shifts(id),
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    status TEXT NOT NULL DEFAULT 'invited',   -- invited | accepted | declined | cancelled | completed | waitlisted
    invite_channel TEXT,
    invite_ts TEXT,
    invited_at TEXT,
    responded_at TEXT,
    UNIQUE (shift_id, volunteer_id)
);
CREATE TABLE IF NOT EXISTS hours_ledger (
    id INTEGER PRIMARY KEY,
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    shift_id INTEGER NOT NULL REFERENCES shifts(id),
    hours REAL NOT NULL,
    logged_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,                       -- sim_response | fill_check | reminder
    due_at TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    done INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events_seen (
    event_id TEXT PRIMARY KEY,
    seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intake_sessions (
    slack_user_id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT '{}',         -- json scratch of parsed fields
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs (done, due_at);
CREATE INDEX IF NOT EXISTS idx_assignments_shift ON assignments (shift_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """One connection per thread; schema applied on first use."""
    path = db_path or config.DB_PATH
    key = f"conn_{path}"
    conn = getattr(_local, key, None)
    if conn is None:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        setattr(_local, key, conn)
    return conn


def row_to_volunteer(row: sqlite3.Row) -> dict:
    v = dict(row)
    for f in ("skills", "certs", "langs", "availability"):
        v[f] = json.loads(v[f] or "[]")
    return v


def row_to_shift(row: sqlite3.Row) -> dict:
    s = dict(row)
    s["requirements"] = json.loads(s["requirements"] or "{}")
    return s


def seen_event(conn: sqlite3.Connection, event_id: str) -> bool:
    """Dedupe: Slack redelivers unacked events. Returns True if already processed."""
    if not event_id:
        return False
    try:
        conn.execute(
            "INSERT INTO events_seen (event_id, seen_at) VALUES (?, ?)", (event_id, now_iso())
        )
        conn.commit()
        return False
    except sqlite3.IntegrityError:
        return True


def add_job(conn: sqlite3.Connection, kind: str, due_at: str, payload: dict) -> int:
    cur = conn.execute(
        "INSERT INTO jobs (kind, due_at, payload) VALUES (?, ?, ?)",
        (kind, due_at, json.dumps(payload)),
    )
    conn.commit()
    return cur.lastrowid


def due_jobs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM jobs WHERE done = 0 AND due_at <= ? ORDER BY due_at", (now_iso(),)
    ).fetchall()
    return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]


def finish_job(conn: sqlite3.Connection, job_id: int) -> None:
    conn.execute("UPDATE jobs SET done = 1 WHERE id = ?", (job_id,))
    conn.commit()


def reset_demo_state(conn: sqlite3.Connection) -> int:
    """Wipe shifts/assignments/jobs/hours and clear volunteer ask-counters, keeping the
    roster. Repeated demo runs at the same time slot otherwise exhaust the pool via
    double-booking exclusions and monthly ask caps. Returns roster size."""
    for table in ("assignments", "shifts", "jobs", "hours_ledger", "intake_sessions"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute(
        "UPDATE volunteers SET last_asked_at = NULL, asks_this_month = 0, active = 1"
    )
    conn.commit()
    return conn.execute("SELECT COUNT(*) c FROM volunteers").fetchone()["c"]
