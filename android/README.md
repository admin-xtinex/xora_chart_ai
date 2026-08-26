# XORA Chart AI — Android

Kotlin + Jetpack Compose client for the same `/api/v1` backend (Web + Android).

## Features

- Opportunities list (pattern, decision APPROVE/WAIT, analysis score)
- Run scan
- Auto demo trades toggle
- Open demo trade on APPROVE
- Trade history + close
- Configurable API base URL

## API base URL

| Environment | Example |
|-------------|--------|
| Android emulator → host machine | `http://10.0.2.2:8030` (default) |
| Physical device (same LAN) | `http://192.168.x.x:8030` |
| Deployed server | `https://your-domain` |

## Build locally

```bash
cd android
gradle assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

Or open the `android/` folder in Android Studio.

## CI artifact

GitHub Actions workflow: `.github/workflows/android-apk.yml`

- Triggers on push to `main` (android paths) or **workflow_dispatch**
- Uploads artifact: **`xora-chart-ai-debug-apk`**

Download from the Actions run → Artifacts.
