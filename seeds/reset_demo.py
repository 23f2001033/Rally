"""Reset to a clean demo state (empty shift board, roster intact, ask-counters cleared).
Run before recording the demo video or before judges test. Run: python -m seeds.reset_demo"""
from rally import db


def main() -> None:
    conn = db.connect()
    conn.execute("DELETE FROM assignments")
    conn.execute("DELETE FROM shifts")
    conn.execute("DELETE FROM jobs")
    conn.execute("DELETE FROM hours_ledger")
    conn.execute("DELETE FROM intake_sessions")
    conn.execute("UPDATE volunteers SET last_asked_at = NULL, asks_this_month = 0")
    n = conn.execute("SELECT COUNT(*) c FROM volunteers").fetchone()["c"]
    conn.commit()
    print(f"Clean demo state: {n} volunteers in roster, no shifts/assignments/jobs.")


if __name__ == "__main__":
    main()
