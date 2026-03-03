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
```

### Health Check

```bash
curl http://localhost:8000/health
# Response: {"status": "ok"}
```

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
