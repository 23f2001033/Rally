"""Seed realistic workspace history into the sandbox so RTS-powered FAQ answers have
material. Requires SLACK_BOT_TOKEN in .env and the bot invited to the channels.

Run AFTER creating channels #logistics #volunteers #events in the sandbox:
    python -m seeds.seed_history
"""
import time

from slack_sdk import WebClient

from rally import config

HISTORY = {
    "logistics": [
        "Reminder for everyone driving Saturday: park in the REAR lot off Mercer St — the front lot is reserved for client pickup. The gate code is 4417.",
        "Warehouse entrance for volunteers is the blue door on the east side. Check in at the desk and grab a vest.",
        "If you're bringing donations, the loading dock is open 8am-4pm weekdays. Ring the bell twice.",
        "Cold storage runs are Tuesdays and Fridays. Drivers need the van keys from the office — ask for Dana.",
        "Please wear closed-toe shoes in the warehouse. Gloves and hairnets are provided at the check-in desk.",
        "Parking update: street parking on Mercer is now 2-hour only. Use the rear lot, it's free for volunteers all day.",
    ],
    "volunteers": [
        "Welcome new folks! Shifts are usually 3-4 hours. Water and snacks are provided, and you can log your hours with Rally for our records.",
        "Q: Do I need food safety certification to sort produce? A: No — only for the repack line. Sorting just needs the 10-min orientation video.",
        "Spanish speakers: we especially need help at the client-facing desk on Saturdays. It makes a huge difference for our families.",
        "If you can't make a shift, no guilt — just tap the button in your confirmation message and Rally finds cover.",
        "Minors 14-17 can volunteer with a signed guardian form (front desk has copies). Under 14 needs a guardian present.",
    ],
    "events": [
        "Recap: last Saturday's food drive served 240 families — a record! Huge thanks to the 11 volunteers who showed up in the rain.",
        "Summer Harvest Festival is Aug 22. We'll need setup crew (morning), servers (midday), and teardown (evening). Rally will coordinate sign-ups.",
        "The school backpack program kicks off July 28 — we'll pack 500 backpacks. Watch this space for shifts.",
    ],
}


def main() -> None:
    client = WebClient(token=config.SLACK_BOT_TOKEN)
    channels = {}
    cursor = None
    while True:
        resp = client.conversations_list(limit=200, cursor=cursor, types="public_channel")
        for c in resp["channels"]:
            channels[c["name"]] = c["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    for name, messages in HISTORY.items():
        ch = channels.get(name)
        if not ch:
            print(f"!! channel #{name} not found — create it and invite the bot, then rerun")
            continue
        for msg in messages:
            client.chat_postMessage(channel=ch, text=msg)
            time.sleep(1.2)  # stay under chat.postMessage rate limits
        print(f"Seeded #{name} with {len(messages)} messages")


if __name__ == "__main__":
    main()
