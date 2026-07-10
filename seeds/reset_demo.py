"""Reset to a clean demo state (empty shift board, roster intact, ask-counters cleared).
Local equivalent of telling Rally "reset the demo". Run: python -m seeds.reset_demo"""
from rally import db


def main() -> None:
    n = db.reset_demo_state(db.connect())
    print(f"Clean demo state: {n} volunteers in roster, no shifts/assignments/jobs.")


if __name__ == "__main__":
    main()
