# Duo Tracker Fix Pack

This build fixes the requested three problems while preserving the existing UI and feature set.

## 1. Multiple independent trackers

- Added a `Tracker` database entity.
- A new account can **Create new** and receives its own Tracker ID.
- A new account can **Join existing** with a friend's Tracker ID.
- Each tracker is limited to two accounts/players.
- Players, projects, custom tabs, backgrounds, AI slots, scores, history, graph data, and exports are tracker-scoped.
- Existing two-player databases are migrated automatically on startup.
- The old first user's code is reused as the legacy Tracker ID where possible.
- A legacy second player is claimed by the first joining account instead of creating a third player.

## 2. Background loading / navigation speed

- The saved background is rendered into the initial HTML by FastAPI, so it is present on first paint.
- Client-side state loading is cached and shared across page scripts.
- Redundant initial state refreshes were removed from page scripts.
- The automatic rivalry banner uses the fast non-AI template path, so a remote AI request no longer runs on every page navigation.

## 3. Logout

- Added a visible desktop sidebar logout button.
- Added a visible mobile navigation logout button.
- Kept the Account page logout button.
- Logout clears the session cookie and protected routes immediately reject the old session.

## 4. Safety for multi-tracker deployment

- Tracker-scoped CSV/JSON export and graph queries were audited.
- Cross-tracker project/tab IDs return 404.
- Manual database-wide backup/restore/delete controls are disabled by default. This prevents one tracker member from restoring or deleting another tracker member's data.
- `ALLOW_GLOBAL_BACKUPS=true` is available only for a trusted server administrator who understands that SQLite snapshots contain all trackers.

## Deployment note

Back up the production database before deploying this build. Keep the existing `.env` file and its `APP_SECRET_KEY`. On restart, the app runs its migration automatically. Do not upload your real `.env`, database, backups, or virtual environment to GitHub.
