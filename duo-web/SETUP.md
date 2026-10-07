# Duo Tracker: beginner setup guide

## 1. Install Python

Install **Python 3.11 or newer** from the official Python website. During Windows installation, enable **Add Python to PATH**.

Check it:

```text
Windows:  py --version
mac/Linux: python3 --version
```

You should see Python 3.11+.

## 2. Create/open the project folder

Download/extract the project, then open a terminal in the `duo-tracker` folder.

### Windows PowerShell

```powershell
cd path\to\duo-tracker
```

### macOS / Linux

```bash
cd /path/to/duo-tracker
```

## 3. Create a virtual environment

A virtual environment keeps Duo Tracker's packages isolated from the rest of your machine.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this only for the current terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 4. Install dependencies

Upgrade pip, then install the exact dependency set declared by the project:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, SQLAlchemy, Jinja2, python-dotenv, upload support, encryption, and the OpenAI-compatible SDK.

## 5. Create `.env`

Copy the example file:

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

Generate a strong application secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `.env` and replace `APP_SECRET_KEY=replace-with-a-long-random-secret` with the generated value.

The remaining defaults are suitable for localhost. You can optionally set `AI_DEFAULT_KEY` and the AI provider defaults, but the recommended path is to add keys from the Settings page.

## 6. Run the server

From the project root, with the virtual environment active:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

What each part means:

- `python -m uvicorn` starts the ASGI server.
- `app.main:app` means: load `app/main.py` and use its `app` object.
- `--reload` restarts the server after code changes during local development.
- `--host 127.0.0.1` keeps it local to your machine.
- `--port 8000` uses port 8000.

Open:

```text
http://127.0.0.1:8000
```

API documentation is also available at:

```text
http://127.0.0.1:8000/docs
```

On first startup, SQLite tables are created automatically and demo data is seeded.

## 7. Reset the demo database

If you want a completely fresh demo dataset:

```bash
python scripts/seed.py
```

Then restart/reload the server.

## 8. Test every feature

### Home

Open `/`.

- Confirm both players appear.
- Edit either player name and click outside the field.
- Click the small emoji button to pick an emoji.
- Click an avatar to upload an image.
- Open **Customize canvas** and try Aurora, Sunset, Ocean, a solid color, and a background image.
- Confirm the page remembers the choice after refresh.
- Click Education, Fitness, Projects, and Leaderboard cards.
- Click **Create New Tab** and create a custom tracker.

### Education

Open `/education`.

- Add a subject and notes for each player.
- Use the bottom daily-total control to set each player's total study minutes.
- Confirm the progress bars change.
- Confirm the 14-day study chart updates after data changes.

The daily total is intentionally separate from study notes because the requested product model has one source of truth for total study time.

### Fitness

Open `/fitness`.

- Log an activity such as Swimming, Walking, or Strength.
- Enter duration in minutes.
- Confirm today's total changes and the chart reflects the logged minutes.

### Projects

Open `/projects`.

- Create multiple project files.
- Open a project.
- Add missions and assign them to either player.
- Complete missions and watch the progress bar animate.
- Add daily progress notes for each player.
- Confirm each player's mission counts appear in parallel.

### Custom tabs

Create one of each tracking type:

- `time log`
- `checklist`
- `notes`
- `numeric counter`

Then add an entry for both players.

### Graph

Open `/graph`.

- Confirm player, project, task, subject, and activity nodes exist.
- Drag nodes.
- Scroll/pinch to zoom.
- Inspect relationships.

### Leaderboard

Open `/leaderboard`.

- Compare today's, weekly, all-time, and streak values.
- Complete a project task or add workout/study time and refresh.
- Download the CSV export.

Point rules in this MVP are intentionally simple:

- Study time: 1 XP per minute.
- Workout time: 1 XP per minute.
- Completed mission: 25 XP.
- Streak bonus: 5 derived XP per consecutive day after the first day.

### Settings / AI

Open `/settings`.

For each AI slot, enter:

- Provider name.
- OpenAI-compatible base URL.
- Model name.
- API key.
- Enabled/disabled state.

Click **Save**, then **Test**.

The browser receives only a masked value such as `sk-****1234`.

To test automatic failover, enable at least two slots, make sure they have working credentials, then click **Test failover**. Slot 1 is artificially treated as failed, so the next enabled slot should be selected.

AI features can then be tested from Home with **Daily recap**, **Study suggestions**, and the rivalry banner.

## 9. Common errors

### `ModuleNotFoundError`

Make sure the virtual environment is active, then run:

```bash
python -m pip install -r requirements.txt
```

### PowerShell says script execution is disabled

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Port 8000 is already in use

Run on another port:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Then open `http://127.0.0.1:8001`.

### `database is locked`

Close duplicate Uvicorn processes and leave only one development server running. SQLite is intentionally used here for the local-first MVP.

### AI test returns 401 / 403 / 429

Check the provider, base URL, model name, API key, and account quota. The failover mechanism only moves on for configured retryable provider failures.

### Charts or graph are blank

The core app is local, but Chart.js and vis-network are loaded from CDNs. A restricted/offline browser may block those resources.

### Avatar/background upload fails

Use PNG, JPEG, WEBP, or GIF. Avatar files are limited to 5 MB and background uploads to 10 MB.

## 10. Multi-tracker accounts

Duo Tracker is now designed for many independent two-person trackers in one deployment.

### Create your own tracker

On `/signup`, choose **Create new**. After account creation, open **Account & code** to see your six-character Tracker ID.

### Join a friend's tracker

On `/signup`, choose **Join existing**, enter your friend's Tracker ID, and create your account. The tracker accepts at most two accounts.

### Data isolation

Players, projects, custom tabs, backgrounds, AI slots, scores, history, and exports are scoped to the active Tracker ID. A user in Tracker A cannot open Tracker B's project or settings by changing an ID in the URL.

### Saved background loading

The saved background is inserted into the server-rendered HTML before the browser paints the page. Client-side state is cached for the current page, duplicate initial state requests are reused, and the automatic rivalry call uses the fast template path rather than an AI request. This prevents the old background flicker and removes an avoidable external AI delay on page navigation.

### Logout

A **Log out** control is available in the desktop sidebar, the mobile navigation, and the Account page.
