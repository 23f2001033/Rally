# Rally — Setup & Run

## Steps only YOU can do (do these tonight — ~30 min)

1. **Register on Devpost**: https://slackhack.devpost.com/ → Register (track: *Slack Agent for Good*).
2. **Join the Slack Developer Program** (free): https://api.slack.com/developer-program/join
3. **Create a developer sandbox**: https://docs.slack.dev/tools/developer-sandboxes/ — this is the workspace judges will test in.
4. **Create the Slack app**: https://api.slack.com/apps → *Create New App* → *From a manifest* → pick your sandbox → paste the contents of [manifest.json](manifest.json).
5. **Tokens** (app settings page):
   - *OAuth & Permissions* → Install to workspace → copy **Bot User OAuth Token** (`xoxb-…`)
   - *Basic Information* → App-Level Tokens → create one with scope `connections:write` → copy (`xapp-…`)
   - *Basic Information* → copy the **Signing Secret**
6. **LLM API key (free)**: https://aistudio.google.com/apikey — Google Gemini free tier, no credit card. (Alternative: https://console.groq.com free tier; switch via the commented lines in `.env`.)
7. Copy `.env.example` → `.env` and fill everything in.
8. In the sandbox, create channels `#logistics`, `#volunteers`, `#events` and `/invite @Rally` to each.
9. Join the hackathon community channel: https://community.slack.com/archives/C0B397ZQ9FS

## Run locally (Socket Mode — no public URL needed)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m seeds.seed_roster      # 30 simulated volunteer personas
python -m seeds.seed_history     # realistic channel history (needs .env + channels above)

python -m rally.app              # start Rally (Socket Mode)
```

## Try it (in Slack)

- Open Rally from the top-left AI/agent entry point (or DM it) and click a suggested prompt, or type:
  - `I need 6 volunteers for the Saturday food drive, 9am-1pm at the warehouse. At least 2 with driver's licenses and 1 Spanish speaker.`
  - Watch the status card fill as simulated volunteers (🤖) respond over ~15 seconds.
  - `simulate a cancellation` → watch the rescue loop re-fill the spot.
  - `Where do I park at the warehouse?` → cited answer from #logistics history (RTS API).
  - `I'd like to sign up as a volunteer.` → intake conversation → Confirm.

## MCP server (Claude Desktop demo)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rally": {
      "command": "C:\\Users\\Aman\\Desktop\\slackhack\\.venv\\Scripts\\python.exe",
      "args": ["-m", "rally.mcp_server"],
      "cwd": "C:\\Users\\Aman\\Desktop\\slackhack",
      "env": {"RALLY_DB_PATH": "C:\\Users\\Aman\\Desktop\\slackhack\\rally.db"}
    }
  }
}
```

Then ask Claude Desktop: *"How's Saturday coverage looking? Who's driving?"*

## Tests

```powershell
python -m pytest tests -q
```

## Before submitting (July 13, by ~1 PM PT)

- Invite `slackhack@salesforce.com` and `testing@devpost.com` to the sandbox; verify they can reach Rally.
- Keep `RALLY_SIMULATION=1` so judges can experience the full loop solo.
- Record demo video (< 3 min, public YouTube) — script in [PLAN.md](PLAN.md) §6.
- Architecture diagram + Devpost write-up with the social-impact statement (stats in [RALLY-REVIEW.md](RALLY-REVIEW.md) §2).
