# Duo Tracker

A two-person self-improvement cockpit. Track study time, fitness activities, projects, and custom habits — with a competitive leaderboard, streak system, and optional AI companion.

![Duo Tracker](app/static/favicon.svg)

---

## Features

- **Multi-tracker competition** — anyone can create a private two-player tracker or join one with its Tracker ID; each tracker is isolated
- **Education tracking** — study sessions with subjects, notes, and time tracking
- **Fitness logging** — activity logs with duration and points
- **Projects** — shared missions with tasks, progress, and notes
- **Custom tabs** — create your own trackers (time log, checklist, notes, numeric counter)
- **Leaderboard** — weekly and all-time rankings with streaks and activity counts
- **Graph view** — Obsidian-style network of your progress ecosystem
- **AI companion** — optional daily recap and study suggestions via any OpenAI-compatible API
- **Data management** — export CSV/JSON, backup/restore, clear history, reset scores
- **Full reset** — with automatic backup and typed confirmation safety
- **Appearance** — Soft Glass / Dark Glass themes with Aurora, Sunset, Ocean gradients

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite via SQLAlchemy 2.x |
| Templates | Jinja2 |
| Frontend | Vanilla HTML/CSS/JavaScript (no build step) |
| AI | OpenAI-compatible API (OpenAI, Groq, xAI, Gemini, etc.) |
| Encryption | Fernet (cryptography library) |

---

## Local Development

### 1. Prerequisites

- Python 3.11 or newer
- pip

### 2. Clone and set up

```bash
git clone <your-repo-url>
cd duo-web-fixed2/duo-web

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set APP_SECRET_KEY to a strong random value
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Run the application

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Or using the Python module form
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

The database is created automatically on first run with demo data for both players.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Application environment |
| `APP_SECRET_KEY` | `dev-only-change-me` | **CHANGE THIS.** Used to encrypt AI API keys in the database |
| `DATABASE_URL` | `sqlite:///./duo_tracker.db` | SQLite path or other SQLAlchemy URL |
| `HOST` | `127.0.0.1` | Server bind host |
| `PORT` | `8000` | Server bind port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `AI_DEFAULT_PROVIDER` | `OpenAI` | Seed provider for slot 1 (first run only) |
| `AI_DEFAULT_BASE_URL` | `https://api.openai.com/v1` | Seed base URL (first run only) |
| `AI_DEFAULT_MODEL` | `gpt-4o-mini` | Seed model (first run only) |
| `AI_DEFAULT_KEY` | _(empty)_ | Seed API key (first run only, stored encrypted) |
| `ALLOW_GLOBAL_BACKUPS` | `false` | Server-admin switch for database-wide backup management; keep `false` for multi-tracker deployments |

> **Security:** `APP_SECRET_KEY` must be set to a strong value in production. If you change it, existing encrypted API keys become unreadable and must be re-entered in Settings. In multi-tracker mode, keep `ALLOW_GLOBAL_BACKUPS=false` so one tracker member cannot restore or delete another tracker's database snapshot.

---

## Database

### Schema

The SQLite database contains these tables:

| Table | Purpose |
|---|---|
| `players` | Player profiles (name, emoji, avatar) |
| `daily_stats` | Per-player per-day study and workout totals |
| `study_entries` | Individual study session records |
| `activity_logs` | Individual fitness activity records |
| `projects` | Project definitions |
| `project_tasks` | Tasks within projects |
| `project_notes` | Notes on projects |
| `custom_tabs` | User-created tracking tabs |
| `custom_tab_entries` | Entries within custom tabs |
| `points_events` | Immutable log of all point-earning events |
| `background_settings` | Theme and background configuration |
| `ai_key_slots` | Encrypted AI provider configurations (3 slots) |

### Database location

By default: `duo-web/duo_tracker.db` (relative to project root).

Customise with `DATABASE_URL` in `.env`.

---

## Data Management

Access tracker-scoped data operations from **Settings → Data Management**. Database-wide SQLite backup management is disabled for normal tracker members in multi-tracker mode.

### Exports

- **Export CSV** — `GET /api/export.csv` — Study entries, activities, project tasks
- **Export JSON** — `GET /api/export.json` — Complete application data (no API keys)

### Data operations

| Operation | What it does | Preserves |
|---|---|---|
| **Reset Scores** | Deletes all points events and daily stats | Players, entries, tabs, settings |
| **Clear History** | Deletes all activity records and stats | Players, tab/project structure, settings |
| **Reset Player Score** | Resets one player's points only | Everything else |
| **Delete Tab** | Removes a custom tab and all its entries | All other data |
| **Full Reset** | Removes all data except players and AI config | Player names/avatars, AI keys, appearance |

> **Full Reset** requires typing `RESET` in a confirmation dialog and automatically creates a database backup first.

### Backups

The automatic safety backup created before a full reset is server-side. Manual database-wide backup/restore/delete controls are disabled by default in multi-tracker mode because a SQLite snapshot contains every tracker in the database. A server administrator can explicitly enable those controls with `ALLOW_GLOBAL_BACKUPS=true`.

Backups are stored in `duo-web/backups/` as timestamped SQLite files:

```
backups/
    duo_tracker_backup_20261006_120000.db
    duo_tracker_backup_20261006_115642.db
```

When `ALLOW_GLOBAL_BACKUPS=true`, Settings can manage those server-wide snapshots. Keep the setting `false` on a public multi-tracker deployment.

### Backup / Restore via CLI

```bash
# Create a manual backup
cp duo_tracker.db backups/duo_tracker_backup_manual.db

# Restore a backup (while server is stopped)
cp backups/duo_tracker_backup_20261006_120000.db duo_tracker.db
```

---

## AI Provider Configuration

AI features are **optional**. The app works fully without any API key.

Configure up to **three provider slots** in Settings → AI Providers. Slots are tried in order (1 → 2 → 3) with automatic failover.

### Supported Providers (any OpenAI-compatible API)

| Provider | Base URL |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| xAI / Grok | `https://api.x.ai/v1` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| Ollama (local) | `http://localhost:11434/v1` |

### Security

- API keys are stored **encrypted** in SQLite using Fernet encryption derived from `APP_SECRET_KEY`
- Keys are **never** returned to the browser in any API response
- JSON exports explicitly exclude all AI key data
- The masked key display (e.g. `sk-****abcd`) is computed server-side

---

## API Reference

The full interactive API documentation is available at:

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Key endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/state` | Full application state |
| `PATCH` | `/api/players/{id}` | Rename player / change emoji |
| `GET` | `/api/leaderboard` | Rankings with streaks and activity counts |
| `GET` | `/api/charts?days=14` | Time series data for charts |
| `POST` | `/api/custom-tabs` | Create custom tab |
| `PATCH` | `/api/custom-tabs/{id}` | Rename custom tab |
| `DELETE` | `/api/custom-tabs/{id}` | Delete tab and all its entries |
| `DELETE` | `/api/education/entries/{id}` | Delete a study entry |
| `DELETE` | `/api/fitness/{id}` | Delete a fitness entry |
| `POST` | `/api/data/reset-scores` | Reset all scores |
| `POST` | `/api/data/clear-history` | Clear all history |
| `POST` | `/api/data/reset-all` | Full reset (requires `{"confirmation":"RESET"}`) |
| `GET` | `/api/export.csv` | Export CSV |
| `GET` | `/api/export.json` | Export JSON (no API keys) |

---

## Production Deployment

### Running with Uvicorn

```bash
# Set environment variables or configure .env
export APP_SECRET_KEY="your-strong-secret-here"
export APP_ENV=production
export HOST=0.0.0.0
export PORT=8000

uvicorn app.main:app --host $HOST --port $PORT --workers 1
```

> Use `--workers 1` with SQLite. For multi-worker deployments, switch to PostgreSQL.

### Running behind a reverse proxy (nginx)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Security checklist for production

- [ ] Set `APP_SECRET_KEY` to a strong random value
- [ ] Keep `.env` out of version control (already in `.gitignore`)
- [ ] Set `APP_ENV=production`
- [ ] Use HTTPS (via reverse proxy + Let's Encrypt)
- [ ] Restrict `HOST` to `127.0.0.1` if behind a proxy
- [ ] Regular database backups (use Settings → Backups or cron job)

---

## Testing

```bash
# Syntax check
python -c "import app.routers.api; import app.services.data_management; import app.services.backup; print('OK')"

# Run with auto-reload for development testing
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Manual test checklist

1. Create custom tab → rename it → delete it
2. Add a study entry → delete it
3. Add a fitness entry → delete it
4. Reset one player's score
5. Reset all scores → verify leaderboard shows 0
6. Clear history → verify entries gone, players remain
7. Create a backup → verify file in backups/
8. Full reset (type RESET) → verify backup auto-created
9. Restore backup → refresh → verify data returned
10. Export CSV → open in spreadsheet
11. Export JSON → verify no api_key/encrypted_key fields
12. Configure AI slot → test connection
13. Test AI failover
14. Verify favicon loads (no 404)
15. Check all pages render without Python tracebacks

---

## Git Commands

```bash
# Stage all changes
git add -A

# Commit
git commit -m "feat: add complete data management system

- Data management: clear-history, reset-scores, reset-all (with RESET confirmation)
- Per-player score reset
- Delete individual study and fitness entries
- Custom tab create, rename, delete
- Backup/restore/delete system with automatic pre-reset backup
- Export CSV and JSON (no API keys in JSON)
- Settings page redesigned: AI, Appearance, Players, Tabs, Data, Backups, Danger Zone
- Favicon 404 fixed
- Leaderboard now shows total_activities
- engine.dispose() after backup restore for clean connection pool
- .env.example updated with provider examples"

# Push
git push origin main
```

---

## Project Structure

```
duo-web/
├── app/
│   ├── main.py              # FastAPI entry point, startup, favicon
│   ├── config.py            # Environment-based configuration
│   ├── db.py                # SQLAlchemy engine and session setup
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response models
│   ├── routers/
│   │   ├── api.py           # All JSON API endpoints
│   │   └── pages.py         # HTML page routes
│   ├── services/
│   │   ├── ai_client.py     # OpenAI-compatible AI client with failover
│   │   ├── backup.py        # Database backup and restore
│   │   ├── data_management.py # Delete, reset, clear, export operations
│   │   ├── rivalry.py       # Rivalry message templates
│   │   ├── scoring.py       # Points, streaks, daily stats
│   │   ├── security.py      # Fernet encryption for API keys
│   │   └── seed.py          # Demo data for first run
│   ├── templates/           # Jinja2 HTML templates
│   └── static/
│       ├── css/app.css      # All styling
│       └── js/              # Per-page JavaScript modules
├── backups/                 # Database backups (auto-created)
├── .env                     # Your local config (gitignored)
├── .env.example             # Config template
├── requirements.txt         # Python dependencies
└── README.md                # This file
```
