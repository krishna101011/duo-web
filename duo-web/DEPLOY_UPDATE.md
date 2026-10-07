# Updating an existing Duo Tracker deployment

1. Make a copy of the current production database before replacing code.
2. Replace the application source with this build. Keep the deployment's existing `.env` values.
3. Make sure `APP_SECRET_KEY` stays the same, otherwise existing encrypted AI keys cannot be decrypted.
4. Redeploy/restart the server. `init_db()` automatically creates the Tracker table and backfills the existing two-player installation into one tracker.
5. Log in with the existing account. Open **Account & code** to see the Tracker ID.
6. Ask the friend to open `/signup`, choose **Join existing**, and enter that Tracker ID.
7. Test another signup with **Create new** to verify that a completely separate tracker is created.
8. Change the background, visit another page, and confirm the same background is visible immediately.
9. Use the main **Log out** button and confirm the app returns to `/login`.
