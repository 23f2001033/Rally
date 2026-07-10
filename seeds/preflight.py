"""Preflight: verify every credential and API surface Rally depends on. Prints PASS/FAIL
per check — never prints secret values. Run: python -m seeds.preflight"""
import sys

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from rally import config


def check(name, fn):
    try:
        detail = fn() or ""
        print(f"  PASS  {name} {detail}")
        return True
    except Exception as e:
        msg = getattr(e, "response", None)
        err = msg["error"] if msg and "error" in getattr(msg, "data", {}) else str(e)[:120]
        print(f"  FAIL  {name}: {err}")
        return False


def main() -> None:
    ok = True
    print("env:")
    for key, val in [("SLACK_BOT_TOKEN", config.SLACK_BOT_TOKEN),
                     ("SLACK_APP_TOKEN", config.SLACK_APP_TOKEN),
                     ("SLACK_SIGNING_SECRET", config.SLACK_SIGNING_SECRET),
                     ("LLM_API_KEY", config.LLM_API_KEY)]:
        present = bool(val and not val.endswith("..."))
        print(f"  {'PASS' if present else 'FAIL'}  {key} {'set' if present else 'MISSING'}")
        ok &= present

    client = WebClient(token=config.SLACK_BOT_TOKEN)
    print("slack:")
    ok &= check("auth.test", lambda: f"-> team '{client.auth_test()['team']}', bot user ok")

    def rts_info():
        resp = client.api_call("assistant.search.info", params={})
        return f"-> {resp.data}"
    ok &= check("assistant.search.info (RTS API)", rts_info)

    def channels():
        found = {c["name"]: c for c in client.conversations_list(
            limit=200, types="public_channel")["channels"]}
        missing = [n for n in ("logistics", "volunteers", "events") if n not in found]
        not_member = [n for n in ("logistics", "volunteers", "events")
                      if n in found and not found[n].get("is_member")]
        if missing:
            raise RuntimeError(f"channels missing: {missing}")
        if not_member:
            raise RuntimeError(f"Rally not invited to: {not_member} — run /invite @Rally there")
        return "-> #logistics #volunteers #events all present, Rally is a member"
    ok &= check("channels + membership", channels)

    print("llm:")
    def llm_ping():
        from rally import llm
        intent = llm.route("I need 5 volunteers for Saturday's food drive at 9am")
        assert intent == "fill_shift", f"unexpected intent: {intent}"
        return f"-> routed to '{intent}'"
    ok &= check(f"chat completion ({config.MODEL_FAST})", llm_ping)

    print("\nAll checks passed — ready to boot." if ok else "\nFix the FAILs above, then rerun.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
