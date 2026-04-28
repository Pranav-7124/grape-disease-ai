# Fix Render Deployment — TODO

## Root Causes
1. No `Procfile` — Render doesn't know how to start the app
2. No `PORT` binding — `app.run(debug=True)` ignores Render's dynamic PORT
3. Missing `/weather_now` and `/forecast` routes — frontend calls these, causing 404/500
4. Database hardcoded to localhost — crashes on Render cloud
5. Debug mode in production

## Tasks
- [x] 1. Create `Procfile`
- [x] 2. Fix `app.py` — PORT binding, add missing routes, production-ready run
- [x] 3. Fix `db.py` — use env vars with safe fallback
- [x] 4. Fix `auth.py` — safe DB import fallback
- [x] 5. Verify `script.js` uses relative URLs

