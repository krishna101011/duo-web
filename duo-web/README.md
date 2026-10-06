# Duo Tracker

Duo Tracker is a local-first, two-person self-improvement tracker built with **Python 3.11+**, **FastAPI**, **SQLAlchemy + SQLite**, **Jinja2**, **vanilla JavaScript**, **Chart.js**, and **vis-network**.

The UI follows the approved **Soft Glass** direction: frosted surfaces, gentle gradients, Sora + DM Mono typography, subtle motion, and a playful rivalry layer.

## Features

- Two players shown side by side across the app.
- Home dashboard with comparison metrics, animated tab cards, editable names, emoji/image avatars, and saved backgrounds.
- Education study entries plus a separate daily total-minute control.
- Simple physical activity logs.
- Project files with aims, assigned missions, daily notes, and calculated progress.
- Custom tabs: time log, checklist, notes, or numeric counter.
- Obsidian-style relationship graph powered by vis-network.
- Weekly and all-time leaderboard with streaks.
- Study, workout, and points charts over time.
- CSV export.
- Optional AI summaries, study suggestions, and AI rivalry text.
- Three-slot encrypted AI key storage with ordered failover and a failover test button.

## Project architecture

The app keeps page routes, JSON API routes, database models, services, templates, and browser scripts separate. There are no hardcoded absolute paths, and deployment-specific values are read from `.env`.

## Security note

AI keys are encrypted before being written to SQLite using a Fernet key derived from `APP_SECRET_KEY`. The browser receives only masked keys and status metadata.

For a production deployment, add real authentication/authorization, CSRF protection, HTTPS, a managed database, and a dedicated object store for uploads.
