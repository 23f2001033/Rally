# Demo video — shot list (target 2:45, hard max 3:00)

Judges weight the video heavily. Keep it tight, show it *working*, end on the MCP "wow."

## Before you hit record
1. **Reset to a clean board:** `python -m seeds.reset_demo`
2. Make sure Rally is running: `python -m rally.app` (or the deployed instance).
3. Have two windows ready: **Slack** (rally workspace, Rally DM open) and **Claude Desktop** (with the Rally MCP server configured — see SETUP.md).
4. Screen-record at 1080p. Use the reset command again between takes if you retry.
5. Optional: put your face-cam or a title card on the first 3 seconds.

## Shot list

**[0:00–0:18] Hook — the problem.** Title card or voiceover over a shot of #volunteers:
> "Every weekend, food banks and shelters fill volunteer shifts with phone trees and spreadsheets. Coordinators lose 6 to 8 hours a week to it, and a third of volunteers no-show. Meet Rally — the coordination agent that lives in Slack."

**[0:18–1:00] Fill a shift.** In Rally's DM, type (or click the suggested prompt):
> `I need 6 volunteers for the Saturday food drive, 9am-1pm at the warehouse. At least 2 with driver's licenses and 1 Spanish speaker.`
Show: Rally's "On it…" reply, the streaming status, then the **live status card** ticking up as 🤖 volunteers accept. Narrate: *"Rally matched the roster by skill and availability, prioritized the drivers and Spanish speaker, and is reaching out — one tap to accept."* Let it reach **6/6 filled**.

**[1:00–1:35] The rescue (the money shot).** Type:
> `simulate a cancellation`
Show: a confirmed volunteer drops, Rally announces it's re-filling, and the card returns to full. Narrate: *"Saturday morning, someone cancels. Rally re-matches and back-fills in seconds — the coordinator gets one calm message instead of a scramble."*

**[1:35–2:05] Volunteer experience + cited answers.** Type:
> `Where do I park at the warehouse?`
Show the cited answer (rear lot / Mercer St) with the source link. Then briefly:
> `I'd like to sign up as a volunteer.`
Show the intake chat turn and the Confirm card. Narrate: *"Volunteers never leave Slack — questions get sourced answers, and joining is a 20-second conversation."*

**[2:05–2:35] The MCP moment.** Switch to **Claude Desktop**. Ask:
> `Using Rally, how's Saturday coverage looking and who's driving?`
Show Claude calling Rally's MCP server and answering from the live roster. Narrate: *"Because Rally exposes its data over MCP, your volunteer HQ is queryable from anywhere your agents live."*

**[2:35–2:45] Close.** Flash the architecture diagram (docs/architecture.svg). Voiceover:
> "Slack is already free for nonprofits. Rally makes it their volunteer HQ — built on Slack's Real-Time Search API, agent surfaces, and MCP."

## Do / don't
- **Do** keep each beat moving; cut dead air while volunteers respond (or speed-ramp it).
- **Do** show real clicks and real responses — judges can tell.
- **Don't** exceed 3:00, use copyrighted music, or show any real personal data.
- Upload to **YouTube (public or unlisted-public)**; paste the link into Devpost and SUBMISSION.md.
