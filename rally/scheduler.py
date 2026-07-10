"""Persisted job loop (RALLY-REVIEW.md R6): due-checks live in SQLite, reconciled on boot,
every handler idempotent. Kinds: sim_response, fill_check, reminder."""
import threading
import time
import traceback

from rally import config, db, outreach, simulation


def _handle(client, conn, job: dict) -> None:
    kind, p = job["kind"], job["payload"]
    if kind == "sim_response":
        simulation.respond(client, conn, p["shift_id"], p["volunteer_id"])
    elif kind == "fill_check":
        outreach.check_fill(client, conn, p["shift_id"])
    elif kind == "reminder":
        shift = outreach.get_shift(conn, p["shift_id"])
        if shift["status"] in ("open", "filled"):
            rows = conn.execute(
                """SELECT v.slack_user_id, v.is_simulated FROM assignments a
                   JOIN volunteers v ON v.id = a.volunteer_id
                   WHERE a.shift_id = ? AND a.status = 'accepted'""",
                (p["shift_id"],),
            ).fetchall()
            for r in rows:
                if not r["is_simulated"]:
                    client.chat_postMessage(
                        channel=r["slack_user_id"],
                        text=f":alarm_clock: Reminder: *{shift['title']}* is coming up "
                             f"({shift['starts_at'].replace('T', ' at ')}). See you there!",
                    )


def run_forever(client) -> None:
    conn = db.connect()
    while True:
        try:
            for job in db.due_jobs(conn):
                db.finish_job(conn, job["id"])  # claim first: a crashing job must not loop forever
                try:
                    _handle(client, conn, job)
                except Exception:
                    print(f"[scheduler] job {job['id']} ({job['kind']}) failed:")
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()
        time.sleep(config.JOB_POLL_SECONDS)


def start(client) -> threading.Thread:
    t = threading.Thread(target=run_forever, args=(client,), daemon=True, name="rally-jobs")
    t.start()
    return t
