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
ADMIN_IDS=YOUR_TELEGRAM_ID
PUBLIC_BASE_URL=https://YOUR_APP.up.railway.app
MINI_APP_URL=https://YOUR_APP.up.railway.app
AGENT_APK_URL=https://github.com/playtowin328-lab/HunterAPIK/releases/download/android-agent-latest/apk-agent.apk
GITHUB_REPO=playtowin328-lab/HunterAPIK
GITHUB_WORKFLOW=android-agent-apk.yml
GITHUB_TOKEN=YOUR_GITHUB_TOKEN_WITH_ACTIONS_PERMISSION
DEVICE_API_TOKEN=GENERATE_LONG_SECRET
STORAGE_DIR=/data
DB_PATH=/data/app.db
DEVICE_TTL_SECONDS=90
PAIRING_TTL_SECONDS=600
MAX_IMAGE_SIZE_MB=20
```

Railway sets `PORT` automatically. Do not hardcode it.

`ADMIN_IDS` locks Telegram bot commands/buttons to specific Telegram users.
Use comma-separated IDs for multiple admins, for example:

```env
ADMIN_IDS=123456789,987654321
```

QR pairing links and device API continue to work after an admin creates a pair code.

`GITHUB_TOKEN` lets the bot start APK builds from Telegram with `/build_apk`.
Create a fine-grained GitHub token for this repository with Actions read/write
and Contents read/write permissions.

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

Or set `AGENT_APK_URL` to a public APK download URL. This repo includes a
GitHub Actions workflow, `Build Android Agent APK`, that publishes:

```text
https://github.com/playtowin328-lab/HunterAPIK/releases/download/android-agent-latest/apk-agent.apk
```

After that release exists, `/agent` will show a working download button and
`/apk-agent.apk` will redirect to the release file.

From Telegram:

```text
/build_apk My Agent
```

If you send an image to the bot before `/build_apk`, that image becomes the APK icon.
The bot starts GitHub Actions, watches the workflow run, and sends the APK
download link or failed run logs when the build finishes.
