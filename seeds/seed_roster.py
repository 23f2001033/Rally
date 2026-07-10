"""Seed the Harvest Table Food Bank demo roster: 30 simulated volunteer personas.
Run: python -m seeds.seed_roster
Idempotent (INSERT OR IGNORE on slack_user_id)."""
import json
import random

from rally import db

FIRST = ["Maya", "Jordan", "Priya", "Luis", "Amara", "Chen", "Fatima", "Dev", "Sofia", "Ken",
         "Nia", "Omar", "Grace", "Hiro", "Elena", "Sam", "Aisha", "Marco", "Tara", "Ivan",
         "Zoe", "Ravi", "Carmen", "Jae", "Lena", "Tunde", "Rosa", "Felix", "Ana", "Noor"]
LAST = ["Patel", "Garcia", "Kim", "Okafor", "Nguyen", "Silva", "Khan", "Lopez", "Chen", "Ali",
        "Reyes", "Mehta", "Osei", "Tanaka", "Ivanov", "Marsh", "Diaz", "Sato", "Bello", "Cruz",
        "Rao", "Vega", "Park", "Ndiaye", "Moro", "Iyer", "Sole", "Haas", "Lund", "Abadi"]
CERTS = ["driver", "first_aid", "food_safety", "forklift"]
LANGS = ["es", "hi", "zh", "fr"]
SKILLS = ["cooking", "sorting", "tutoring", "admin", "setup", "photography", "translation"]
AVAIL = ["weekday_morning", "weekday_afternoon", "weekday_evening",
         "weekend_morning", "weekend_afternoon", "weekend_evening"]


def main() -> None:
    rng = random.Random(42)  # deterministic roster across reseeds
    conn = db.connect()
    created = 0
    for i in range(30):
        name = f"{FIRST[i]} {LAST[i]}"
        certs = rng.sample(CERTS, k=rng.choices([0, 1, 2], weights=[3, 5, 2])[0])
        if i < 8 and "driver" not in certs:  # guarantee enough drivers for the demo ask
            certs.append("driver")
        langs = rng.sample(LANGS, k=rng.choices([0, 1], weights=[6, 4])[0])
        if i % 5 == 0 and "es" not in langs:  # and Spanish speakers
            langs.append("es")
        availability = rng.sample(AVAIL, k=rng.randint(2, 4))
        if i < 20 and "weekend_morning" not in availability:  # demo shift is Sat morning
            availability.append("weekend_morning")
        cur = conn.execute(
            """INSERT OR IGNORE INTO volunteers
               (slack_user_id, name, skills, certs, langs, availability, active, is_simulated, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?)""",
            (f"SIM-{i:03d}", name,
             json.dumps(rng.sample(SKILLS, k=rng.randint(1, 3))), json.dumps(certs),
             json.dumps(langs), json.dumps(availability), db.now_iso()),
        )
        created += cur.rowcount
    conn.commit()
    total = conn.execute("SELECT COUNT(*) c FROM volunteers").fetchone()["c"]
    drivers = conn.execute("SELECT COUNT(*) c FROM volunteers WHERE certs LIKE '%driver%'").fetchone()["c"]
    es = conn.execute("SELECT COUNT(*) c FROM volunteers WHERE langs LIKE '%\"es\"%'").fetchone()["c"]
    print(f"Roster: {total} volunteers ({created} new) — {drivers} drivers, {es} Spanish speakers")


if __name__ == "__main__":
    main()
