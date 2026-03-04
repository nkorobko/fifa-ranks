# FIFA Ranks

FIFA 2v2 player ranking tracker with TrueSkill algorithm.

## Features

- Log 2v2 FIFA match results
- Individual player rankings using TrueSkill
- Weekly Power Index (WPI) composite rankings
- Match history and trends
- Balanced team generator
- Weekly awards
- Telegram bot interface

## Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Database:** SQLite with WAL mode
- **Rating Algorithm:** openskill (TrueSkill implementation)
- **Frontend:** Jinja2 templates + HTMX
- **Hosting:** Railway / Render free tier

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn backend.app.main:app --reload
```

Visit http://localhost:8000 — you should see the app running.

### Docker

```bash
# Build and run
docker-compose up

# Server runs at http://localhost:8000
# Telegram bot starts automatically (requires TELEGRAM_BOT_TOKEN)
```

### Health Check

```bash
curl http://localhost:8000/health
# Response: {"status": "ok"}
```

## Telegram Bot Setup

The Telegram bot is the **primary way to log matches**.

### 1. Create a Bot

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot`
3. Choose a name (e.g., "FIFA Ranks")
4. Choose a username (e.g., "your_office_fifa_bot")
5. Copy the bot token (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your bot token
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. Run the Bot

```bash
# With Docker (recommended)
docker-compose up

# Or manually
python -m backend.bot.main
```

### 4. Start Logging Matches

Add the bot to your office group chat, then:

```
/match Noam Itay vs Ayal Ari 3-1
/rank
/stats Noam
/teams Noam Itay Ayal Ari
```

See `/help` for all commands.

## Bot Commands

| Command | Example | Description |
|---------|---------|-------------|
| `/match` | `/match Noam Itay vs Ayal Ari 3-1` | Log a match result |
| `/rank` | `/rank` | Show current power rankings |
| `/stats` | `/stats Noam` | Player stats and rating |
| `/teams` | `/teams Noam Itay Ayal Ari` | Suggest balanced 2v2 matchups |
| `/streak` | `/streak` | Everyone's current win/loss streak |
| `/today` | `/today` | All matches played today |
| `/undo` | `/undo` | Delete last match (with confirmation) |
| `/help` | `/help` | List all commands |

## Project Structure

```
fifa-ranks/
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── main.py          # FastAPI app
│       ├── config.py        # Settings
│       ├── models.py        # SQLAlchemy models (coming soon)
│       ├── routes/          # API endpoints (coming soon)
│       └── services/        # Business logic (coming soon)
├── frontend/
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
├── docs/
│   └── system-design.md     # Full architecture doc
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Roadmap

See [GitHub Issues](https://github.com/nkorobko/fifa-ranks/issues) for the full roadmap.

**Phase 1: Backend Foundation**
- [x] Project scaffolding (#1)
- [ ] Database schema (#2)
- [ ] Match logging API (#3)
- [ ] Player API (#4)
- [ ] TrueSkill engine (#5)

**Phase 2: Rankings & Analytics**
- [ ] Weekly Power Index (#6)
- [ ] Rankings API (#7)
- [ ] Pair stats (#8)
- [ ] Team generator (#9)

**Phase 3: Frontend**
- [ ] Base layout (#10)
- [ ] Log match form (#11)
- [ ] Power rankings page (#12)
- [ ] Player profiles (#13)
- [ ] Dashboard (#14)
- [ ] Weekly awards (#15)

**Phase 4: Polish**
- [ ] Match editing (#16)
- [ ] Deployment (#17)
- [ ] CI/CD (#18)
- [ ] Cron jobs (#19)
- [ ] Documentation (#20)
- [ ] Telegram bot (#26)

## Players

- Noam
- Itay
- Ayal
- Ari
- Sharon
- Dori

## License

MIT
