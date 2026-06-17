# Deploy to Railway

## 1. GitHub

Create a GitHub repository and push this project.

```bash
git init
git add .
git commit -m "Prepare Railway deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Do not commit `.env`, `storage/`, databases, logs, or screen frames.

## 2. Railway

1. Open Railway.
2. Create a new project.
3. Choose `Deploy from GitHub repo`.
4. Select this repository.
5. Add a public domain.
6. Add a Volume for persistent SQLite/screens.

Recommended volume mount path:

```text
/data
```

This repository also contains the Android agent source. Railway must build only
the Python bot/web service, so `nixpacks.toml`, `runtime.txt`, and
`.railwayignore` are included to force a Python build and skip Android/Gradle
files during deploy.

## 3. Railway Variables

Set these variables:

```env
BOT_TOKEN=YOUR_BOT_TOKEN
PUBLIC_BASE_URL=https://YOUR_APP.up.railway.app
MINI_APP_URL=https://YOUR_APP.up.railway.app
DEVICE_API_TOKEN=GENERATE_LONG_SECRET
STORAGE_DIR=/data
DB_PATH=/data/app.db
DEVICE_TTL_SECONDS=90
PAIRING_TTL_SECONDS=600
MAX_IMAGE_SIZE_MB=20
```

Railway sets `PORT` automatically. Do not hardcode it.

## 4. BotFather

Set the bot Web App / Mini App URL:

```text
https://YOUR_APP.up.railway.app
```

## 5. Healthcheck

Open:

```text
https://YOUR_APP.up.railway.app/health
```

Expected:

```json
{"ok": true, "service": "apk-converter-bot"}
```

## 6. Android Agent

After deploy:

1. Send `/pair` to the bot.
2. Open the pair link on Android.
3. Start the agent.
4. Open the mini app in Telegram.

## 7. Android APK download

The server exposes:

```text
https://YOUR_APP.up.railway.app/agent
https://YOUR_APP.up.railway.app/apk-agent.apk
```

These links work after an APK exists in one of these locations:

```text
mini_app/apk-agent.apk
/data/apk-agent.apk
```

If you do not have Android Studio locally, run the GitHub Actions workflow
`Build Android Agent APK`, download the `apk-agent-debug` artifact, rename
`app-debug.apk` to `apk-agent.apk`, and put it in `mini_app/` before deploy.
