# Design Review: Drawbacks, Memory Architecture, Reliability, Competition

> **STATUS: The "Recall" idea reviewed here was DROPPED on July 10, 2026.** Reasons: (1) Slack's native AI already ships cited Q&A over workspace history; (2) passive decision-detection required LLM analysis of every message — paying to analyze mostly unimportant discussion. The replacement project is **Rally** (volunteer coordination agent, Agent for Good track) — see [PLAN.md](PLAN.md). The memory-architecture decision (§3) and reliability engineering (§4) below still apply and carry over to Rally.

Companion to [PLAN.md](PLAN.md). Written July 10, 2026 — before finalization.

---

## 1. Competitive landscape (what already exists)

| Product | What it does | Overlap with Recall v1 | Agentic? |
|---|---|---|---|
| **Slack native AI** (2026: enterprise search, recaps, new Slackbot agent) | Cited answers over workspace history — literally demos *"What did the team decide about the Q3 launch?"* → sourced answer. Channel recaps, thread summaries. Slackbot personal agent rolling out early 2026. | **HIGH — kills our "ask anything about history" hero feature.** Judges are Slack employees; they know this exists. | Yes (platform-native) |
| **Question Base** | Detects questions in channels, auto-answers from Slack history + Notion/Drive/Confluence, captures expert answers into FAQs. Claims 60–90% repeat-question deflection. | **HIGH — kills our P2 "duplicate-question deflection" feature.** | Partially |
| **ClearFeed / Albus / Dashworks / Guru / Glean** | RAG answer-bots in Slack over indexed docs + conversations. Crowded, mature market ($24–550/mo products). | Medium — generic "answers in Slack" space is saturated. | Partially |
| **Loqbooq / Decision Tracker / Decision Desk** | Decision logs in Slack — slash commands (`/decide`), message actions, PDF/ADR export, review reminders. | Low-Medium — they own "decision log in Slack" but are **100% manual form-filling. Zero AI. Zero extraction. No MCP. No Q&A.** | **No** |
| **Current hackathon gallery** | Not published yet — can't see competing submissions. Assume multiple "answer questions from history" bots will be submitted (it's the obvious idea). | — | — |

### The white space

Nobody — not Slack, not the RAG bots, not the decision-log tools — does **agentic decision memory**:
AI that *detects the moment a decision happens in conversation*, extracts it into a structured, first-class object (decision, rationale, alternatives, owners), manages its lifecycle (active → superseded → deprecated, review reminders), and serves it back **anywhere via MCP**. Manual decision logs die of non-adoption (Loqbooq's own retrospective admits logging discipline is the hard part) — an agent that does the logging *for* you is the fix to the exact failure mode that killed the manual tools.

**Conclusion: pivot the hero feature from "ask anything about workspace history" (commoditized by Slack AI) to "the agent that captures and curates your team's decisions" (empty niche).** RTS API stays central but changes role: from search-as-answer to **search-as-context** — when logging a decision, the agent searches for related past discussions and prior decisions to link; when answering, it grounds in the curated ledger first, live workspace search second.

---

## 2. Drawbacks of Recall v1 — and the fixes

| # | Drawback | Severity | Fix |
|---|---|---|---|
| D1 | **Slack AI already does cited Q&A over history.** "Improvement over existing solutions" is a judged criterion; this fails it head-on. | Critical | Reposition (see above). Q&A remains but as *"ask the decision ledger"* — answers grounded in curated, structured decisions (deterministic, auditable), enriched by live RTS search. State the positioning vs Slack AI explicitly in the write-up: *complementary — built on Slack's own RTS + agent surfaces, producing the durable artifact Slack AI doesn't.* |
| D2 | **Question Base owns question-deflection.** | High | **Cut deflection entirely** (was P2). Don't compete where an incumbent has years of tuning. |
| D3 | **Manual decision logging never sticks** — the adoption failure that killed manual log tools. If Recall requires a shortcut invocation every time, it inherits the same disease. | High | **Agentic auto-detection**: in channels it's invited to, the agent recognizes decision moments ("let's go with B", "agreed, shipping Friday") and posts a *one-click confirm card* (bounded autonomy — suggests, never writes silently). Human confirms → logged. Detection uses cheap fast model on message events. |
| D4 | **RTS API policy: never store retrieved data, never train on it.** Can't build a vector index of workspace messages (which is how all the RAG competitors work — also our compliance differentiator). | Medium | Memory stores only **agent-synthesized, human-confirmed artifacts** (decision summaries + permalinks + metadata). RTS is called live per interaction. Within-request reuse only, no persistence of raw results. Say this in the write-up — privacy-first architecture is a judging asset. |
| D5 | **Cold start** — empty ledger on day 1. | Medium | (a) Value from minute one via live RTS-grounded answers; (b) **backfill mining**: "@Recall mine #platform for past decisions" → RTS retrieves candidate threads live → agent extracts → human confirms each → only the confirmed summaries are stored. Kills cold start *and* makes a great demo beat. |
| D6 | **Latency** — search → read threads → synthesize could take 15–30s. | Medium | Streaming status updates ("Searching #platform… reading 3 threads…"), parallel `conversations.replies` fetches, model tiering (fast model routes/extracts, strong model synthesizes), cap agent loop at 4 tool iterations, prompt caching for the system prompt. |
| D7 | **Hallucinated citations** — one wrong permalink in the demo = credibility gone. | High | **Citation whitelist**: the model may only cite message `ts` values actually returned by tools this turn; permalinks generated programmatically via `chat.getPermalink`, never by the LLM. Below confidence threshold → "I couldn't find a reliable answer" + offer to search wider. |
| D8 | **Demo depends on seeded sandbox data**; semantic search quality on synthetic data unknown. | Medium | Day-0 spike: `assistant.search.info` to confirm semantic availability; corpus written keyword-findable as fallback; 20 **golden questions** regression-tested before recording. |
| D9 | **3-day scope risk.** | High | Cut lines re-drawn (§5). MCP server is small (FastMCP, 3 tools, ~1 hr). Deflection cut. Digest demoted. |
| D10 | **"Yet another bot" skepticism.** | Low | Native surfaces only (assistant thread, canvas, shortcuts) — no external web app. The AccessOwl lesson: business plausibility; the pitch includes who pays (eng orgs, compliance-heavy teams — decision records are an audit artifact). |

---

## 3. Agent memory: options and recommendation

### What Recall actually needs from memory
1. **Session/working memory** — the current assistant-thread conversation.
2. **Long-term structured memory** — the decision ledger (the product itself).
3. **Semantic recall over our own artifacts** — find related/prior decisions.
4. **Temporal validity** — decisions supersede each other; "what's our current stance?" must resolve to the *active* decision, not the 2024 one.
5. Constraint: **no storage of raw Slack data** (D4), 3-day build, single small service.

### Options considered

| Framework | Strengths | Why not (for this build) |
|---|---|---|
| **Mem0** (managed/OSS, ~47k stars) | Drop-in `add()/search()`, auto fact-extraction, vector+graph+KV | Black-box extraction of *generic* memories — we need a first-class decision schema, not loose facts. Extra service, extra latency, extra failure mode in a 72-hour window. Weaker temporal reasoning (benchmarks: ~49% vs Zep's ~64% on LongMemEval temporal queries). |
| **Zep / Graphiti** | Temporal knowledge graph with fact-validity windows — conceptually *exactly* our supersession model | Heavy (graph DB + service) for what reduces to one `status` column and a `superseded_by` foreign key. Wrong cost/benefit at hackathon scale. |
| **Letta (MemGPT)** | Self-editing memory, long-running agents | It's a whole agent framework — replaces our Bolt+Claude loop rather than complementing it. |
| **LangMem / LangGraph** | Checkpointing, memory utilities | Framework lock-in and moving parts we don't otherwise need. |
| **DIY: purpose-built ledger** | Exact schema, deterministic, inspectable, zero extra infra | Must build retrieval ourselves — but that's ~100 lines with FTS5 + sqlite-vec. |

### Recommendation: three-layer, boring-tech memory

1. **Working memory = Slack itself (stateless server).** On every turn, rebuild context from `conversations.replies` on the assistant thread. Slack is the durable store; the service holds nothing between requests → restarts/redeploys are free, no session bugs possible. This is the single biggest reliability win available.
2. **Long-term memory = a purpose-built decision ledger.** SQLite via **sqlite-vec + FTS5** (or Postgres + pgvector if the host prefers): `decisions(id, title, decision, rationale, alternatives, owners, channel, source_permalink, decided_at, status[active|superseded|deprecated], superseded_by, embedding)`. Hybrid retrieval = FTS5 keyword ∪ vector cosine, re-ranked, filtered to `status='active'` by default. This gives us Graphiti's temporal-validity *concept* in ~50 lines of SQL — and "we designed a temporal decision ledger" is a far better judging story than "we called a memory API."
3. **Episodic recall = RTS API, live.** The workspace's raw history is queried fresh on every interaction — never indexed, never stored. This is both policy compliance and the privacy differentiator vs every RAG competitor.

(Stretch, P2, cut freely: per-user preferences — "always answer me in bullet points" — a tiny `user_prefs` KV table. Not worth mem0 for this.)

---

## 4. Reliability & efficiency engineering

**Event handling (the classic Slack-app failure modes):**
- Ack every event within 3 s; do real work async (Bolt lazy listeners / background queue). Slack **retries** unacked events → dedupe by `event_id` (in-memory LRU + DB unique constraint).
- Idempotent writes: unique constraint on source `thread_ts` — the same thread can't produce duplicate ledger entries no matter how many retries fire.

**Grounding & trust:**
- Citation whitelist (D7). Permalinks via `chat.getPermalink`, never model-generated.
- Confidence gate: refuse + escalate ("want me to search all channels?") rather than guess.
- Bounded autonomy: agent proposes, human confirms, for every write (ledger entries, canvas edits).

**Latency & cost:**
- Model tiering: fast model (Haiku) for decision-moment detection + routing + extraction; strong model (Sonnet) for synthesis only.
- Parallel thread fetches; ≤4 tool-loop iterations; truncate thread context to relevant windows; Anthropic prompt caching on the (large) system prompt.
- Rate limits: exponential backoff + jitter on all Slack calls; RTS results reused within a request (allowed) but never persisted.

**Verification before demo:**
- **Golden-question eval**: 20 Q&A pairs + 5 decision-extraction cases against the seeded workspace; scripted run; must pass before recording video. Re-run after any prompt change.
- Degraded-path tests: RTS down, LLM timeout, empty ledger, permission-denied channel.

**Ops during judging (Jul 14 – Aug 6):**
- Paid tier on Render/Fly (no cold-sleep), `/health` endpoint + UptimeRobot ping, structured per-interaction trace logs, nightly SQLite backup to object storage, second test account walkthrough before submitting.

---

## 5. Final recommended shape (pending your sign-off)

**Name:** Recall *(fine to keep; alternatives: Ledger, Precedent, Minute)*
**Pitch:** *"Every team makes its most important decisions in Slack — and loses them in scrollback. Recall is the agent that catches decisions as they happen, keeps them alive, and serves them to any AI that asks."*
**Track:** New Slack Agent (unchanged).

Re-prioritized features:
- **P0** — ① Decision capture: message-shortcut + auto-detected decision moments → confirm card → ledger + per-channel Canvas. ② Ask-the-ledger Q&A with citation-whitelisted answers, enriched by live RTS search. ③ Agent-surface polish (assistant thread, streaming status, suggested prompts).
- **P1** — ④ MCP server (`search_decisions`, `get_decision`, `ask_team_memory`) demoed from Claude Desktop. ⑤ Backfill mining ("mine #eng for past decisions"). ⑥ Lifecycle: supersede links + stale-decision review nudges.
- **P2 (cut freely)** — weekly digest; user preferences. **Deflection: deleted.**

Demo beats (2:45): decision happens live in a thread → Recall notices → one click → structured ledger + canvas ➜ new teammate asks "why are we on Postgres not Mongo?" → cited answer with permalink to the argument ➜ "mine #design for past decisions" backfill ➜ Claude Desktop queries the ledger over MCP ➜ architecture flash.

**Open items to finalize:** ① approve the decision-first pivot, ② name, ③ Bolt Python vs JS (recommend Python — cleanest `Assistant` class + FastMCP synergy). Then PLAN.md gets rewritten to match and Day 0 starts.
