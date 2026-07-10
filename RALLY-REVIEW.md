# Rally — Pre-Finalization Stress Test

Written July 10, 2026. Companion to [PLAN.md](PLAN.md). Predecessor autopsy: [REVIEW.md](REVIEW.md).

---

## 1. THE RULES QUESTION: Must we use Slack's own AI?

**No. Any model is allowed.** Verified against the [official rules](https://slackhack.devpost.com/rules):

- The only technology mandate: *"must develop an application that uses at least one (1) of these technologies: Slack AI capabilities, MCP server integration, or real-time search API."*
- On external services: *"If a Project integrates any third-party SDK, APIs and/or data, Entrant must be authorized to use them"* — i.e., third-party AI APIs are **explicitly permitted** with proper authorization (a normal API key = authorized).
- No requirement to run on Slack/Salesforce infrastructure; no ban on paid services; "Slack AI capabilities" is not even strictly defined.

**Rally's compliance is belt-and-suspenders:** it uses the **RTS API** (FAQ answers, people-finding) *and* an **MCP server** (roster/shift tools) — two unambiguous qualifying technologies — plus Slack's agent surfaces (assistant threads, suggested prompts, statuses), which arguably counts as a third. The reasoning model being Claude API is entirely fine. (If we wanted judge-brownie-points we could *add* an Agentforce touchpoint, but it's not required and not worth the time.)

---

## 2. IS IT REALLY NEEDED? (Impact validation with numbers)

Published industry data says the pain is real and quantifiable:

| Evidence | Number | Source |
|---|---|---|
| Coordinator time on scheduling & comms alone | **6–8 hrs/week** | VolunteerHub |
| Messages to schedule ONE event of 10–15 volunteers | **20–30 back-and-forths** | Volunteer Matrix |
| No-show rate with manual/inconsistent reminders | **~30%** | VolunteerHub |
| No-show rate with automated reminders | **10–15%** (i.e., roughly halved) | VolunteerHub |
| Coordinators reporting burnout as a major concern | **40%** | VolunteerHub |
| Volunteers a typical coordinator manages | **50–200** | VolunteerHub |
| Annual volunteer-base churn (poor communication a top cause) | **20–25%** | Bloomerang |

Impact model for the submission: a coordinator managing ~100 volunteers spends ~300–400 hrs/yr on scheduling logistics; Rally automates the outreach/confirm/rescue/remind loop → most of that time returns to mission work, and automated confirmation+reminder flows alone are documented to cut no-shows by half. Distribution: Slack Pro is **free for nonprofits ≤250 members**, so target orgs can adopt at $0 with volunteers already in the workspace — no new logins (the documented adoption killer for external volunteer platforms).

**Verdict: the need is real, measurable, and the track (Agent for Good → nonprofit operations) exists precisely for it.**

---

## 3. COMPETITION — deeper sweep (anything similar already built?)

| Category | Products | Verdict |
|---|---|---|
| Slack Marketplace shift/rotation bots | RosterBird, TurnShift, Tellspin, Shifter, Rotation App, "Shift Scheduling" | **Closest adjacency — must position against.** All built for *fixed small teams rotating duties* (on-call, standup order). No skill/certification matching, no large opt-in pools, no outreach/confirmation loop, no rescue, no natural language, zero AI. |
| Volunteer management SaaS | When I Work, Golden, Bloomerang Volunteer, POINT, SignUpGenius, VolunteerHub, Mobilize | External websites; Slack used at most for notification pings (via Zapier/Workato). Separate logins = adoption killer. |
| Corporate volunteering in Slack | Millie | Employee-giving programs for companies — different buyer, different problem. |
| Open source | astoria-tech/volunteer-dispatch (COVID-era, Airtable-watching) | Abandoned; not agentic; proves the need existed. |
| Slack native AI | Slackbot agent, enterprise search | General assistant; does not do goal-directed multi-party coordination (outreach → confirm → rescue). No overlap with the core loop. |

**Differentiation sentence for the write-up:** "Rotation bots schedule a fixed team in a circle; Rally recruits from a 200-person opt-in pool by skill, certification, and availability, pursues the fill as a goal, and repairs it when humans flake."

---

## 4. DRAWBACKS AND FIXES

| # | Drawback | Severity | Fix |
|---|---|---|---|
| R1 | **Judge testability.** Judges evaluate solo in our sandbox — one person can't be coordinator + 6 volunteers. Stage One judging is pass/fail viability; if a judge can't see the loop work, we fail there. | **Critical** | **Simulation mode built in from Day 1**: seeded volunteer personas auto-respond to outreach with realistic delays (clearly labeled "🤖 simulated volunteer — demo mode"). A `Try Rally` guided path (suggested prompt) walks the judge through fill → rescue in 2 minutes as coordinator. Also our own demo-video rig. |
| R2 | **"Workflow, not agent" perception.** SQL matching + templated DMs could read as a workflow app; the challenge is an *Agent* Builder Challenge. | High | Add the **negotiation beat**: when a shift can't be filled as specified, Rally reasons about trade-offs and proposes options ("Only 4 licensed drivers are free Saturday. I can: (a) fill 6 with 1 driver, (b) fill 5 with 2 drivers, (c) ask #general beyond the roster. Which?"). Goal persistence + constraint reasoning + bounded autonomy = agent, visibly. Goes in the demo. |
| R3 | **Outreach DMs = spam risk.** Judges at Slack care deeply about agent etiquette; an agent that blasts DMs reads badly. | High | Opt-in at intake; max one outreach per volunteer per shift; batching when multiple shifts target the same person; quiet hours; a "pause my volunteering" button on every outreach. Etiquette is a *feature* in the write-up (bounded autonomy — Slack's own stated agent design principle). |
| R4 | **Free-text intake → bad matching.** "I can drive the van sometimes" must become queryable data. | Medium | Haiku normalizes to a controlled tag vocabulary (skills, certs, availability windows), then **echoes back for confirmation** ("Got you down for: driver ✓ · Spanish ✓ · weekend mornings ✓ — correct?"). Human-confirmed structure only. |
| R5 | **Availability modeling rabbit hole.** Recurring calendars/timezone math could eat a full day. | Medium | Coarse availability tags only (weekday/weekend × morning/afternoon/evening). The Accept/Decline button *is* the true availability check. No calendar integration in v1. |
| R6 | **Scheduler fragility.** In-process timers (escalation deadlines, reminders) die on restart → silent failure to escalate. | Medium | Due-checks persisted in a SQLite `jobs` table; reconciled on boot; every job idempotent. (Same discipline as REVIEW.md §4 event dedupe.) |
| R7 | **Fairness/burnout in matching.** Naive SQL always picks the same eager volunteers → over-ask burnout (the 20–25% churn problem, reproduced by our own tool). | Medium | Order candidates by least-recently-asked + monthly ask-cap. One line of SQL; a whole paragraph of retention story for the write-up. |
| R8 | **Double-booking.** Volunteer accepted for overlapping shifts. | Low | Exclusion constraint in the matching query; checked again at accept time. |
| R9 | **PII sensitivity.** Roster holds availability/skills of real people. | Low | Minimal data, no documents (driver's license = boolean tag), volunteer self-service: "show my info" / "delete my data" DM commands. Privacy paragraph in submission. |
| R10 | **Thin history for RTS FAQ** in young workspaces (and our sandbox). | Low | Seeded #logistics history; RTS file search over pinned docs/canvases; graceful fallback: "I couldn't find that — I've asked a coordinator in #volunteers" (escalation, not hallucination). |
| R11 | **Someone else builds a volunteer agent in the Good track.** | Unknowable | Win on execution: simulation mode, negotiation reasoning, etiquette, impact numbers, and all-three-techs coverage are hard to replicate in a rushed build. |

---

## 5. RELIABILITY & EFFICIENCY (consolidated)

**Efficiency — the cost design the previous idea failed on:**
- **Zero passive compute.** Triggers are exclusively: DM to the agent, @mention, button click, or a due job for a shift Rally owns. It never reads ambient channel traffic.
- LLM budget per operation: intake ≈ 3–5 Haiku turns; shift request parse ≈ 1 Haiku call; negotiation proposal ≈ 1 Sonnet call; FAQ ≈ 1 RTS call + 1 Sonnet call. Outreach/reminders/status updates: **0 LLM calls** (templates + SQL). Filling a 6-person shift ≈ **single-digit cents**.
- Prompt caching on system prompts; ≤4 tool iterations hard cap.

**Reliability (carrying REVIEW.md §4 forward, plus Rally-specific):**
- 3s event acks, async work, `event_id` dedupe (Slack redelivers), idempotent writes (unique volunteer+shift).
- Persisted job queue (R6); citation whitelist + programmatic permalinks for FAQ answers.
- Golden-path rehearsal script: fill → accept → cancel → rescue → FAQ → MCP query, run against the deployed instance before recording and again before submitting; degraded-path checks (RTS down, LLM timeout, empty roster).
- Paid-tier hosting + uptime ping through the Aug 6 judging window; nightly DB backup.

---

## 6. VERDICT

- **Rules risk: cleared** — any LLM allowed; Rally uses two-to-three qualifying Slack technologies regardless.
- **Need: validated with published numbers** (6–8 coordinator-hours/week, ~30% no-shows halved by automation, 40% coordinator burnout).
- **Competition: white space holds** after a second, deeper sweep; nearest neighbors are team-rotation bots with zero AI and no volunteer semantics.
- **Drawbacks: all addressable**, and the two big ones (judge simulation mode, negotiation reasoning) actually *raise* the ceiling of the submission rather than just patching holes.

**Recommendation: finalize Rally as specified in PLAN.md, with R1 (simulation mode) and R2 (negotiation beat) promoted into P0.** Roughly 2.5 days remain; the schedule in PLAN.md §5 absorbs both promotions (simulation mode replaces some multi-account demo rigging; negotiation is one extra Sonnet prompt + one Block Kit card).
