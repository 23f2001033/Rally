# Deploying Rally (keep it live for judging: Jul 14 – Aug 6)

Rally uses **Socket Mode**, so it needs no public URL or inbound ports — it runs as an
always-on worker that connects out to Slack. It must stay running for the whole judging
window so judges can test the sandbox anytime.

## Recommended: Fly.io (free allowance, always-on, persistent disk)

One-time setup:
```powershell
# 1. Install flyctl
iwr https://fly.io/install.ps1 -useb | iex
# 2. Sign up / log in (free; a card is required to prevent abuse but the small VM is free)
fly auth signup    # or: fly auth login
```

Deploy from the project folder:
```powershell
cd C:\Users\Aman\Desktop\slackhack
fly launch --no-deploy --copy-config --name rally-volunteer-agent   # accepts fly.toml
fly volumes create rally_data --size 1 --region iad                 # persistent SQLite

# Set secrets (NEVER commit these). Paste your real values:
fly secrets set `
  SLACK_BOT_TOKEN=xoxb-... `
  SLACK_APP_TOKEN=xapp-... `
  SLACK_SIGNING_SECRET=... `
  LLM_API_KEY=AIza...

fly deploy
fly logs        # should show "Rally is running (Socket Mode)"
```

That's it — the roster self-seeds on first boot. Redeploys keep data (volume-backed).

### Alternative: Railway (no card, ~$5/mo free credit — enough for one month)
1. Push this repo to GitHub (see below).
2. railway.app → New Project → Deploy from GitHub → pick the repo.
3. Settings → set the 4 env vars above. Railway auto-detects the Dockerfile.
4. Add a Volume mounted at `/data` (Settings → Volumes) so SQLite persists.

## Push to GitHub first (needed for Railway; good hygiene anyway)
```powershell
cd C:\Users\Aman\Desktop\slackhack
git add -A
git commit -m "Rally: volunteer coordination agent"
# create an EMPTY repo on github.com, then:
git branch -M main
git remote add origin https://github.com/<you>/rally.git
git push -u origin main
```
`.gitignore` already excludes `.env` and `rally.db`, so no secrets are pushed. Verify with
`git status` before pushing.

## The MCP demo stays local
The MCP server (`python -m rally.mcp_server`) runs on **your machine** over stdio for the
Claude Desktop demo — it is not deployed. Config in [SETUP.md](SETUP.md).

## Uptime check (optional but wise)
Fly keeps the machine on. For peace of mind during judging, run `fly status` daily, or add a
tiny external uptime monitor that pings `fly logs` health. If it ever dies: `fly deploy` again.
