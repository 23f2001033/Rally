"""Live end-to-end test against the real sandbox. Creates a real shift, sends real invites
(simulated volunteers only — no human DMs), lets the RUNNING server's job loop process
responses, then triggers a cancellation rescue, FAQ, and intake-contract checks.
Everything visible in #volunteers. Run while `python -m rally.app` is up.
"""
import sys
import time

from slack_sdk import WebClient

from rally import config, db, faq, llm, matching, outreach

client = WebClient(token=config.SLACK_BOT_TOKEN)
conn = db.connect()
REPORT = []


def step(name, fn):
    try:
        detail = fn() or ""
        print(f"  PASS  {name} {detail}")
        REPORT.append((name, True, detail))
        return True
    except Exception as e:
        print(f"  FAIL  {name}: {type(e).__name__}: {e}")
        REPORT.append((name, False, str(e)))
        return False


def main():
    # setup: find the human coordinator + #volunteers
    humans = [u for u in client.users_list()["members"]
              if not u.get("is_bot") and not u.get("deleted") and u["id"] != "USLACKBOT"]
    coordinator = humans[0]["id"]
    channels = {c["name"]: c["id"] for c in client.conversations_list(types="public_channel")["channels"]}
    vol_ch = channels["volunteers"]
    print(f"coordinator: {humans[0].get('real_name') or humans[0]['name']} ({coordinator}); stage: #volunteers")

    client.chat_postMessage(channel=vol_ch, text=":test_tube: *Live test starting* — watch this channel.")

    # 1. LLM shift parsing
    shift_holder = {}
    def parse():
        p = llm.parse_shift_request(
            "I need 6 volunteers for the Saturday food drive, 9am-1pm at the warehouse. "
            "At least 2 with driver's licenses and 1 Spanish speaker.")
        assert "error" not in p, p
        assert p["needed"] == 6 and p["requirements"].get("certs", {}).get("driver") == 2, p
        shift_holder["parsed"] = p
        return f"-> {p['title']} {p['starts_at']} needed={p['needed']} reqs={p['requirements']}"
    if not step("LLM parses shift request", parse):
        sys.exit(1)

    # 2. create shift + plan + invites (server's job loop will process sim responses)
    def fill():
        shift = outreach.create_shift(conn, shift_holder["parsed"], coordinator, vol_ch, None)
        shift_holder["id"] = shift["id"]
        plan = matching.plan_invites(conn, shift)
        assert plan["invite"], "no eligible volunteers"
        n = outreach.send_invites(client, conn, shift, plan["invite"])
        outreach.post_or_update_status_card(client, conn, outreach.get_shift(conn, shift["id"]))
        return f"-> shift #{shift['id']}, invited {n}, feasible={plan['feasible']}"
    if not step("matching + outreach wave", fill):
        sys.exit(1)

    # 3. wait for the RUNNING SERVER to process simulated responses to filled
    def wait_filled():
        for i in range(30):
            time.sleep(3)
            s = outreach.get_shift(conn, shift_holder["id"])
            p = matching.shift_progress(conn, shift_holder["id"])
            if s["status"] == "filled":
                return f"-> filled {len(p['accepted'])}/{s['needed']} after ~{(i+1)*3}s (server job loop)"
        raise TimeoutError(f"not filled; progress={ {k: len(v) for k, v in p.items()} }")
    step("live server fills the shift", wait_filled)

    # 4. rescue: a confirmed simulated volunteer cancels
    def rescue():
        from rally import simulation
        name = simulation.cancel_random_accepted(client, conn, shift_holder["id"])
        assert name, "no simulated accepted volunteer found"
        for i in range(30):
            time.sleep(3)
            s = outreach.get_shift(conn, shift_holder["id"])
            p = matching.shift_progress(conn, shift_holder["id"])
            if s["status"] == "filled" and len(p["accepted"]) >= s["needed"]:
                return f"-> {name} cancelled; re-filled after ~{(i+1)*3}s"
        raise TimeoutError("rescue did not re-fill")
    step("dropout rescue re-fills", rescue)

    # 5. FAQ via RTS API (bot token, no action_token — may require one; finding either way)
    def faq_test():
        ans = faq.answer(client, "Where do I park at the warehouse?")
        client.chat_postMessage(channel=vol_ch, text=f":mag: *FAQ test:* Where do I park?\n{ans}")
        assert "rear" in ans.lower() or "mercer" in ans.lower() or "couldn't" in ans.lower(), ans[:200]
        assert "http" not in ans or "slack.com" in ans, "unexpected link domain"
        return f"-> {ans[:110]!r}"
    step("FAQ via RTS API", faq_test)

    # 6. intake JSON contract (LLM only, no Slack writes)
    def intake_test():
        from rally import intake
        r1 = llm.intake_turn({}, "Hi, I'd like to volunteer! I'm free on weekend mornings and I can drive.")
        assert "say" in r1 and "state" in r1, r1
        # Assert against the app's actual normalization path (what gets stored).
        state = intake.normalize_state(r1["state"])
        assert "weekend_morning" in state["availability"], state
        assert "driver" in state["certs"], state
        return f"-> captured {state}"
    step("intake conversation contract", intake_test)

    passed = sum(1 for _, ok, _ in REPORT if ok)
    summary = f"{passed}/{len(REPORT)} checks passed"
    client.chat_postMessage(channel=vol_ch, text=f":test_tube: *Live test finished:* {summary}")
    print(f"\n{summary}")


if __name__ == "__main__":
    main()
