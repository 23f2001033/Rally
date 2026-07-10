"""Block Kit builders. Templates only — no LLM calls in this module."""
from datetime import datetime


def fmt_when(shift: dict) -> str:
    start = datetime.fromisoformat(shift["starts_at"])
    end = datetime.fromisoformat(shift["ends_at"])
    return f"{start.strftime('%A %b %d, %I:%M%p').replace(' 0', ' ')} – {end.strftime('%I:%M%p')}"


def invite_blocks(shift: dict, volunteer: dict) -> list[dict]:
    req_note = ""
    reqs = shift.get("requirements") or {}
    wanted = [t for t in (volunteer["certs"] + volunteer["langs"])
              if t in (reqs.get("certs") or {}) or t in (reqs.get("langs") or {})]
    if wanted:
        req_note = f"\n_You're a match because of: {', '.join(wanted)}_"
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": (f":wave: Hi {volunteer['name'].split()[0]}! Can you help with "
                     f"*{shift['title']}*?\n:calendar: {fmt_when(shift)}"
                     + (f"\n:round_pushpin: {shift['location']}" if shift.get("location") else "")
                     + req_note)}},
        {"type": "actions", "block_id": f"invite_{shift['id']}", "elements": [
            {"type": "button", "style": "primary", "action_id": "accept_shift",
             "text": {"type": "plain_text", "text": "I'm in ✅"}, "value": str(shift["id"])},
            {"type": "button", "action_id": "decline_shift",
             "text": {"type": "plain_text", "text": "Can't this time"}, "value": str(shift["id"])},
            {"type": "button", "action_id": "pause_volunteering",
             "text": {"type": "plain_text", "text": "Pause my volunteering"}, "value": "pause"},
        ]},
    ]


def status_card_blocks(shift: dict, progress: dict) -> list[dict]:
    accepted, invited = progress["accepted"], progress["invited"]
    needed = shift["needed"]
    filled = len(accepted) >= needed
    bar = "█" * min(len(accepted), needed) + "░" * max(needed - len(accepted), 0)

    def names(people):
        return ", ".join(p["name"] + (" 🤖" if p["is_simulated"] else "") for p in people) or "—"

    header = ":white_check_mark: *Filled!*" if filled else ":hourglass_flowing_sand: *Filling…*"
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"{shift['title']}"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": (f"{header}  `{bar}`  *{len(accepted)}/{needed}*\n"
                     f":calendar: {fmt_when(shift)}"
                     + (f"\n:round_pushpin: {shift['location']}" if shift.get("location") else ""))}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Confirmed ({len(accepted)})*\n{names(accepted)}"},
            {"type": "mrkdwn", "text": f"*Awaiting reply ({len(invited)})*\n{names(invited)}"},
        ]},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "🤖 = simulated volunteer (demo mode) · Rally re-fills automatically if anyone cancels"}]},
    ]


def accepted_blocks(shift: dict) -> list[dict]:
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": (f":tada: You're confirmed for *{shift['title']}* — {fmt_when(shift)}."
                     "\nIf anything changes, tap below and I'll find cover. No guilt!")}},
        {"type": "actions", "elements": [
            {"type": "button", "action_id": "cancel_attendance", "style": "danger",
             "text": {"type": "plain_text", "text": "I can't make it anymore"},
             "value": str(shift["id"])}]},
    ]


def intake_confirm_blocks(state: dict) -> list[dict]:
    def tags(key):
        return ", ".join(state.get(key) or []) or "none"
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": (":clipboard: *Here's what I'll record:*\n"
                     f"• Availability: {tags('availability')}\n"
                     f"• Certifications: {tags('certs')}\n"
                     f"• Languages: {tags('langs')}\n"
                     f"• Skills: {tags('skills')}\n"
                     "_You can say \"show my info\" or \"delete my data\" anytime._")}},
        {"type": "actions", "elements": [
            {"type": "button", "style": "primary", "action_id": "confirm_intake",
             "text": {"type": "plain_text", "text": "Confirm ✅"}},
            {"type": "button", "action_id": "restart_intake",
             "text": {"type": "plain_text", "text": "Start over"}}]},
    ]


def negotiation_blocks(shift: dict, summary: str, options: list[dict]) -> list[dict]:
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f":thinking_face: *{shift['title']}* can't be filled as specified.\n{summary}"}},
    ]
    for i, opt in enumerate(options[:3]):
        blocks.append({"type": "section",
            "text": {"type": "mrkdwn", "text": f"*{opt['label']}* — {opt['description']}"},
            "accessory": {"type": "button", "action_id": f"negotiate_{i}",
                          "text": {"type": "plain_text", "text": opt["label"][:24]},
                          "value": f"{shift['id']}:{opt['action']}"}})
    return blocks
