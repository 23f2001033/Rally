# Rally — the Volunteer Coordination Agent for Nonprofits on Slack

**Hackathon:** [Slack Agent Builder Challenge](https://slackhack.devpost.com/) · Deadline: **July 13, 2026, 5:00 PM PT**
**Track:** **Slack Agent for Good** (nonprofit operations — an explicitly listed track theme)
**One-liner:** Nonprofits run on Slack but coordinate volunteers by phone tree and spreadsheet. Rally is the agent that fills shifts, rescues dropouts, answers volunteer questions with citations, and turns hours into grant-ready impact reports — entirely inside Slack, entirely on-demand.

> Predecessor idea "Recall" (institutional memory agent) was dropped on July 10 — see [REVIEW.md](REVIEW.md). Fatal flaws: Slack's native AI already ships cited Q&A over history, and passive decision-detection meant paying LLM costs to analyze every message, mostly noise. Rally is designed to avoid both: validated white space + **100% on-demand economics**.

---

## 1. The real problem

Thousands of nonprofits get **Slack Pro free** (orgs ≤250 members) via Slack for Nonprofits — so their volunteers are already in Slack. But coordination is stone-age:

- Filling a weekend shift = mass @channel posts, phone trees, and a SignUpGenius link half the volunteers never open.
- A Saturday-morning cancellation = the coordinator personally texting down a list.
- "Where do I park?" / "What should I bring?" answered for the 40th time.
- Hours tracking for grant reports = a spreadsheet nobody updates.

Every existing tool (When I Work, Golden, Bloomerang, POINT, SignUpGenius) is an **external website** with its own logins — the #1 adoption killer for volunteers who just want to help. Nothing Slack-native and agentic exists (verified July 10: closest matches are Millie, a *corporate* employee-giving app, and an abandoned open-source Airtable-dispatch bot).

## 2. Why this wins

| Criterion | Rally's case |
|---|---|
| **Technological Implementation** | All three qualifying techs: agent surfaces (assistant thread, streaming status, suggested prompts), **RTS API** (cited FAQ answers from workspace history; finding people from past messages), **MCP server** (roster/shifts queryable from Claude Desktop). Plus a *genuine* agentic loop: given a goal ("fill this shift"), it plans, acts, monitors, and re-plans on dropouts — with human escalation. |
| **Design** | Volunteers never leave Slack: conversational intake in DM, Accept/Decline buttons, live-updating shift card, event Canvas. Coordinator talks to it in natural language. |
| **Potential Impact** | Track-perfect: nonprofit operations. Deployable at **zero cost** to any Slack-for-Nonprofits org. Time saved = mission delivered; hours ledger = grant reporting evidence. |
| **Quality of Idea** | Validated empty niche. Incumbents are external SaaS; Rally is Slack-native + agentic. Clear "improvement over existing solutions" story. |

**Track odds:** Agent for Good almost certainly draws far fewer entries than New Slack Agent (the default track for 4,096 participants). Same $8k/$4k prizes.

**Cost economics (the Recall lesson, fixed by design):**
- Agent acts **only when invoked** — a DM, a mention, a button click, or an active shift it owns. Zero passive message analysis, ever.
- Matching = SQL queries, not LLM calls. Outreach DMs = templates. LLM used only to (a) parse a coordinator's natural-language request (Haiku), (b) run intake conversations (Haiku), (c) synthesize cited FAQ answers (Sonnet, only on explicit questions).
- Estimated LLM cost per filled shift: cents.

## 3. Features

### P0 — the demo core
1. **Conversational intake.** Volunteer DMs Rally → short guided chat ("What days work? Any skills — driving, languages, first aid?") → structured roster entry (skills, availability, languages, certifications). Modal-form fallback if conversation flow gets buggy.
2. **Agentic shift filling.** Coordinator: *"@Rally I need 6 volunteers for the Saturday food drive, 9am–1pm — at least 2 with driver's licenses and 1 Spanish speaker."* → Rally parses → queries roster → DMs best matches with Accept/Decline buttons → tracks live on a status card in the coordinator's thread → widens the pool or escalates if under-filled by a deadline it sets with the coordinator.
3. **Dropout rescue.** Volunteer taps "Can't make it anymore" → Rally instantly re-matches, reaches out, back-fills, and notifies the coordinator. *(The money demo moment.)*

### P1 — qualifying-tech showcases
4. **Cited FAQ answers (RTS API).** "Where do I park at the warehouse?" → `assistant.search.context` over workspace history + pinned logistics → answer with permalink citations. On-demand only.
5. **Event Canvas.** Auto-generated per shift: roster, roles, logistics, updated live as confirmations land.
6. **MCP server (FastMCP):** `find_volunteers`, `get_shift_status`, `log_hours`, `impact_summary` — demoed from Claude Desktop ("How's Saturday's coverage looking?").

### P2 — cut freely
7. **Impact ledger.** Confirmed shifts → hours per volunteer → monthly grant-ready impact digest (a SUM query + one canvas — cheap to build, big narrative value; promote if time allows).
8. Google Sheets roster import (MCP client).

## 4. Architecture

```
Slack workspace (sandbox: fake food bank "Harvest Table")
  │ on-demand triggers only: DM, app_mention, button actions, shortcuts
  ▼
Bolt for Python (single service; Render/Fly paid tier)
  ├── Request parser + intake chat ... claude-haiku (cheap, fast)
  ├── FAQ synthesis w/ citation whitelist ... claude-sonnet (only on questions)
  ├── Matching engine ... pure SQL, no LLM
  ├── Outreach + tracking ... templated DMs, Block Kit actions,
  │        scheduled re-checks via APScheduler (fill-deadline monitoring)
  ├── Store: SQLite — volunteers(skills, availability, langs, certs),
  │        shifts, assignments(status), hours_ledger
  │        (no vector DB needed at all — matching is structured;
  │         FAQ uses RTS live, nothing raw ever persisted)
  └── MCP server (FastMCP/HTTP, bearer-token auth): 4 tools
```

- **Memory (per REVIEW.md decision, now even simpler):** stateless working memory — rebuild conversation from `conversations.replies` per turn; long-term memory = the structured roster/shift/ledger DB. No memory framework, no embeddings.
- **Scopes:** `chat:write`, `im:history`, `im:write`, `app_mentions:read`, `assistant:write`, `search:read.public`, `search:read.files`, `canvases:write`, `commands`, `users:read`.
- **Reliability carried over from REVIEW.md §4:** 3s event acks + async work, `event_id` dedupe, idempotent assignment writes (unique volunteer+shift), citation whitelist + programmatic permalinks, backoff+jitter, golden-path rehearsal before recording, uptime ping through Aug 6 judging.

## 5. Three-day plan (now ~2.5 days)

### Tonight, July 10
- [ ] Devpost registration; Slack Developer Program + sandbox; join hackathon channel.
- [ ] Scaffold Bolt Python app (Assistant class), SQLite schema, deploy skeleton.
- [ ] Seed script: "Harvest Table Food Bank" workspace — ~30 fake roster volunteers (DB), realistic channel history (#logistics, #volunteers, #events) so RTS FAQ answers have material; 2–3 real test accounts for live demo interactions.
- [ ] De-risk: `assistant.search.info` semantic-search check; one end-to-end DM round trip.

### Day 1, July 11 — the agentic core
- [ ] Coordinator request parsing → SQL matching → outreach DMs with buttons → live status card.
- [ ] Dropout rescue loop + under-filled escalation (APScheduler check).
- [ ] Volunteer intake conversation → roster write.
- [ ] Event Canvas generation.

### Day 2, July 12 — showcases + polish + deploy
- [ ] RTS-cited FAQ answers; suggested prompts; home tab.
- [ ] FastMCP server + Claude Desktop rehearsal.
- [ ] Impact ledger if on schedule.
- [ ] Deploy paid tier; invite `slackhack@salesforce.com` + `testing@devpost.com`; full golden-path rehearsal (all flows, degraded paths).
- [ ] Evening: record demo takes.

### Day 3, July 13 — submission (deadline 5 PM PT)
- [ ] Final video < 3 min; architecture diagram; Devpost write-up **including the required social-impact statement**; submit by ~1 PM PT.

## 6. Demo script (2:45)

1. **0:00–0:20 Hook.** "Every weekend, food banks fill volunteer shifts with phone trees and spreadsheets. Meet Rally." *(Show the chaos: an @channel plea in #volunteers.)*
2. **0:20–1:05 Fill a shift.** Coordinator asks Rally for 6 volunteers incl. 2 drivers → DMs go out → status card ticks up live → shift filled, Canvas appears.
3. **1:05–1:35 The rescue.** A volunteer cancels Saturday morning → Rally re-matches and back-fills in seconds → coordinator gets one calm notification instead of a crisis.
4. **1:35–2:00 Volunteer experience.** New volunteer intake by DM; then "where do I park?" → cited answer from #logistics history (RTS).
5. **2:00–2:25 MCP beat.** Claude Desktop: "How's Saturday coverage? Who's driving?" → answers from Rally's MCP server.
6. **2:25–2:45 Impact + close.** Monthly hours/impact digest ("214 volunteer hours — export for your grant report"). "Slack is already free for nonprofits. Rally makes it their volunteer HQ."

## 7. Risks

| Risk | Mitigation |
|---|---|
| Multi-account demo complexity | 2–3 real test accounts in browser profiles for live beats; 30 DB-seeded volunteers make matching look rich; record beats separately and cut |
| Block Kit state bugs in intake | Modal-form fallback path built Day 1 |
| Timezone/date parsing rabbit holes | Store shift times as plain local strings; no TZ math |
| RTS semantic quality on seeded data | Tonight's spike; keyword-findable corpus fallback |
| Scope (2.5 days) | P0 alone is a winnable demo; P1 items are independent bolt-ons; P2 pre-approved cuts |

## 8. Submission checklist

- [ ] Track: **Slack Agent for Good** + social-impact explanation
- [ ] Text description of features & functionality
- [ ] Demo video < 3 min, public YouTube
- [ ] Architecture diagram
- [ ] Sandbox URL, access for `slackhack@salesforce.com` + `testing@devpost.com`
- [ ] Submit before July 13, 5:00 PM PT
