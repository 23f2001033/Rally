# Devpost submission — copy/paste fields

**Project name:** Rally
**Tagline:** The volunteer coordination agent that lives in Slack — fills shifts, rescues dropouts, and turns hours into grant-ready impact.
**Track:** Slack Agent for Good (nonprofit operations)
**Qualifying technologies used:** Real-Time Search API · MCP server · Slack agent surfaces (all three)

---

## Elevator pitch (≤200 chars)
Nonprofits live in Slack but coordinate volunteers by phone tree and spreadsheet. Rally is the agent that fills shifts by skill, auto-rescues cancellations, and answers volunteer questions with sources.

---

## Inspiration
Thousands of nonprofits get Slack Pro free, so their volunteers are already in Slack — but coordination is stuck in the stone age. Published sector data says it plainly: volunteer coordinators spend **6–8 hours every week** just on scheduling and messaging, scheduling a single event of 10–15 people takes **20–30 back-and-forth messages**, and **~30% of volunteers no-show** when reminders are manual — a rate that automated reminders cut roughly in half. **40% of coordinators report burnout.** Every existing tool (When I Work, Golden, Bloomerang, SignUpGenius) is an external website with its own logins — the number-one adoption killer for volunteers who just want to help. We wanted the coordination to happen where the people already are: in Slack, and driven by an agent instead of a spreadsheet.

## What it does
Rally is an agent, not a form. A coordinator asks in plain language — *"I need 6 volunteers for the Saturday food drive, 9am–1pm, at least 2 with driver's licenses and 1 Spanish speaker"* — and Rally:

- **Matches** the opt-in roster by skill, certification, and availability (prioritizing scarce requirements first), then **reaches out** with one-tap Accept/Decline DMs and tracks confirmations on a **live status card**.
- **Rescues dropouts automatically:** when someone taps "I can't make it anymore," Rally instantly re-matches, back-fills the slot, and sends the coordinator one calm notification instead of a crisis.
- **Negotiates when it can't fill as specified:** *"Only 4 licensed drivers are free Saturday — I can fill 6 with 1 driver, 5 with 2, or post an open call. Which?"* — goal-directed reasoning, with the human always in control.
- **Answers volunteer questions with citations** ("Where do I park?") using Slack's Real-Time Search API over workspace history.
- **Onboards volunteers by conversation:** a short DM chat becomes a structured roster entry.
- **Reports impact:** confirmed hours roll into a grant-ready summary, queryable from **any MCP client** (we demo it live from Claude Desktop).

## How we built it
- **Bolt for Python** on **Socket Mode** — one always-on worker, no inbound URL needed.
- **Real-Time Search API** (`assistant.search.context`) for cited FAQ answers, with a `conversations.history` fallback so answers work even without an action token.
- An **MCP server** (FastMCP) exposing `find_volunteers`, `get_shift_status`, `log_hours`, `impact_summary` — the roster and coverage become tools any agent can call.
- **Slack agent surfaces**: assistant threads, suggested prompts, streaming status.
- **Gemini** (free tier) as the reasoning model — tiered (a fast model routes/parses, a stronger model synthesizes) with retry + automatic cross-model fallback so a model outage never breaks an answer.
- **SQLite** for the roster, shifts, hours ledger, and a persisted job queue (escalations/reminders survive restarts).
- **Simulation mode**: seeded volunteer personas auto-respond so a solo judge can experience the full multi-party fill-and-rescue loop without recruiting six people.

## Efficiency & etiquette (by design)
Rally acts **only on demand** — a DM, a mention, a button, or a job for a shift it owns. It never scans ambient channel traffic, so it costs nothing when idle. Matching is pure SQL; outreach and reminders are templates; the LLM is used only to parse a request, run an intake chat, or synthesize an answer — single-digit cents per filled shift. Outreach is opt-in, ask-capped per volunteer per month, and ordered least-recently-asked so the same eager people don't burn out.

## Challenges we ran into
- **Free-tier model churn:** mid-competition, our first Gemini models were retired (404) and the newest one rate-limited hard. We moved to Google's floating `-latest` aliases and built retry-plus-cross-model-fallback so a model going down can never break a user-facing answer.
- **Solo-judge testability:** an agent whose whole value is coordinating *many* people is hard to evaluate alone — so we built simulation mode.
- **Real-Time Search auth:** RTS needs an action token from a user event; we added a channel-history fallback so the FAQ never dead-ends.

## Accomplishments we're proud of
A genuinely agentic loop (plan → act → monitor → re-plan on failure) that a nonprofit could deploy today at zero cost, with the human in control at every write. Full test coverage: 13 unit tests plus a live end-to-end suite that passes 6/6 against a real sandbox.

## What we learned
Design for the free tier and for the solo evaluator from day one; make the agent's autonomy *bounded and visible* (it proposes, humans confirm); and turn constraints (no data storage, no passive reads) into differentiators (privacy, cost).

## What's next
Recurring shifts and calendar sync, a Slack Marketplace listing, multi-org support, and pulling roster data from existing volunteer CRMs via MCP.

## Built with
`python` · `slack-bolt` · `socket-mode` · `real-time-search-api` · `mcp` · `fastmcp` · `gemini` · `sqlite` · `block-kit`

---

## Social impact statement (required for Agent for Good)
Rally targets nonprofit operations — an explicitly named theme of the Agent for Good track. Volunteer coordinators are among the most time-starved people in the social sector; the hours Rally gives back (6–8 per week, per coordinator) convert directly into mission delivery, and its automated confirm-and-remind loop is documented to roughly halve volunteer no-shows, meaning food banks, shelters, and community programs actually get the help they scheduled. Because Slack is free for nonprofits under 250 members and Rally adds no new logins for volunteers, the barrier to adoption is near zero. The impact ledger doubles as grant-reporting evidence, easing the administrative burden that small nonprofits carry. Rally makes the tool nonprofits already have — Slack — into their volunteer HQ.

## Testing access for judges (put in the submission's sandbox/access field)
- Sandbox workspace URL: **<paste your rally sandbox URL>**
- Access granted to: `slackhack@salesforce.com` and `testing@devpost.com`
- To try it: open Rally from the top-bar agent entry point (or DM it) and use a suggested prompt. Simulation mode is ON — send *"I need 6 volunteers for the Saturday food drive, 9am-1pm, 2 with driver's licenses and 1 Spanish speaker"*, watch it fill, then send *"simulate a cancellation"* to see the rescue. Ask *"Where do I park at the warehouse?"* for a cited answer.
- Demo video: **<paste YouTube link>**
- Code: **<paste GitHub link>**
