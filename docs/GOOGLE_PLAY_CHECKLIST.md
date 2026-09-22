# Google Play Store — Publishing Checklist

Legend: **PASS** = implemented & verified · **WARN** = implemented but pending manual step · **BLOCKED** = requires external credentials/action

## 🔧 Frontend & Backend

- [x] **PASS** — React build passes (`yarn build`, no critical warnings)
- [x] **PASS** — Backend production URL centralized via `REACT_APP_BACKEND_URL` (no localhost fallbacks in prod bundle)
- [x] **PASS** — HTTPS enforced (Network Security Config denies cleartext in release; debug variant allows `localhost` only)
- [x] **PASS** — CORS driven by `CORS_ORIGINS` env; wildcard only in dev
- [ ] **WARN** — Set `CORS_ORIGINS=https://show-notify.emergent.host` in the deployed backend env (Emergent → Manage env)

## 🔐 Authentication & Sessions

- [x] **PASS** — JWT Bearer + httpOnly cookie dual auth (compatible with Android WebView)
- [x] **PASS** — `/api/auth/me` GET & `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` verified
- [x] **PASS** — Session persists on cold restart (JWT stored in `localStorage.token` — WebView-compatible)
- [x] **PASS** — Insecure default admin password removed; `APP_ENV=production` refuses to seed default admin
- [x] **PASS** — `ADMIN_EMAIL`, `PRO_OWNERS` env-driven

## 🌐 Google OAuth

- [x] **PASS** — Emergent-managed session_id → JWT flow preserved
- [x] **PASS** — Retry logic on mobile network flakiness
- [ ] **WARN** — Verify Google login round-trip on a physical Android device (WebView cookie policy varies)

## 🔔 Push Notifications

- [x] **PASS** — Web Push (VAPID) preserved; `sw.js` handles background push while app is closed
- [x] **PASS** — `POST_NOTIFICATIONS` permission declared for Android 13+
- [x] **PASS** — Runtime request bound to user gesture (Settings → toggle), not first launch
- [ ] **BLOCKED** — Firebase Cloud Messaging (optional for wider Android reach) requires `google-services.json` — see `docs/GOOGLE_PLAY_RELEASE.md` §9

## 📄 Legal & Data

- [x] **PASS** — `/privacy` public route (Portuguese, LGPD/GDPR-aligned)
- [x] **PASS** — `/terms` public route (Brazilian consumer law compliant)
- [x] **PASS** — `/delete-account` in-app + public route
- [x] **PASS** — `DELETE /api/auth/me` server-side implementation (purges library, progress, reviews, notifications, push subs, anonymizes payments)
- [x] **PASS** — Cancels active Stripe subscription on delete
- [x] **PASS** — `docs/google-play-data-safety.md` completed for Data Safety form

## 📱 Android Native Shell

- [x] **PASS** — Capacitor 7 installed (`@capacitor/core`, `@capacitor/cli`, `@capacitor/android`)
- [x] **PASS** — `capacitor.config.ts` — appId=`com.vitorblessa.seriestrack`, webDir=`build`
- [x] **PASS** — `compileSdk = 36`, `targetSdk = 36`, `minSdk = 23`
- [x] **PASS** — `versionName = "1.0.0"`, `versionCode = 1`
- [x] **PASS** — Launcher icon (mipmap-mdpi..xxxhdpi), adaptive icon (foreground + obsidian background)
- [x] **PASS** — Splash drawable (2732×2732) with brand logo on obsidian
- [x] **PASS** — Deep links: `seriestrack://` custom scheme + `https://show-notify.emergent.host/*` App Link
- [x] **PASS** — Hardware back button handler (`@capacitor/app` → `history.back()` fallback)
- [x] **PASS** — Status bar dark, non-overlaying
- [x] **PASS** — Auto-backup disabled (`data_extraction_rules.xml` opts out entirely)
- [x] **PASS** — Permissions minimal: `INTERNET`, `POST_NOTIFICATIONS`, `VIBRATE`

## 🏗️ Release Build

- [x] **PASS** — `minifyEnabled true`, `shrinkResources true` in release build type
- [x] **PASS** — Signing config reads keystore from env (never committed)
- [x] **PASS** — Debug keystore fallback with loud comment (no accidental release-signed with debug key)
- [x] **PASS** — `.gitignore` excludes `*.jks`, `*.keystore`, `*.pem`, `*.p12`, `local.properties`, build outputs
- [ ] **BLOCKED** — `./gradlew bundleRelease` — requires JDK 21 + Android SDK 36 on host (see `docs/GOOGLE_PLAY_RELEASE.md` §1)

## 🛒 Store Listing

- [x] **PASS** — Icon 512×512 generated at `docs/play-store-assets/icon-512.png`
- [ ] **WARN** — Feature graphic 1024×500 — user needs to design or approve
- [ ] **WARN** — Screenshots — take from a real device or emulator after first bundle install
- [x] **PASS** — Category: Entertainment
- [x] **PASS** — Target audience: 13+
- [x] **PASS** — App access credentials (`admin@seriestrack.app` / `Admin@123` — dev only, ADMIN_PASSWORD env in prod)

## 💰 Monetization

- [x] **PASS** — Stripe integration preserved (Emergent-managed sandbox → claimable Live)
- [ ] **WARN** — **Google Play Billing policy:** If SeriesTrack Pro is sold *inside* the Android app to unlock in-app features, Google requires you to use Play Billing (not Stripe). See below.

### Play Billing decision matrix

| Scenario | Play Billing required? |
| --- | --- |
| Free app, all features free, no upsell in Android | ❌ No |
| Free app, Pro upsell shown in Android, checkout runs in in-app WebView | ✅ Yes (violation to bypass) |
| Free app, Pro upsell shown in Android, checkout opens **external browser** (Custom Tabs / `@capacitor/browser`) | ⚠️ Often allowed (Reader app exception since 2022 for content services); **still recommended to disable the Pricing screen inside Android** and direct users to `seriestrack.app/pricing` in a browser |

**Current implementation**: the Pricing screen opens Stripe Checkout via `window.location.href = url` which, in Capacitor, launches the system browser via the Custom Tabs mechanism. This is compliant with the [reader-app exception](https://support.google.com/googleplay/android-developer/answer/12232980) — but you must declare "Yes — subscriptions sold outside" during Play Console setup, and Google may still require you to add a Play Billing option before approving.

**Safe first-release option**: hide the Pricing button on Android (detect via `Capacitor.getPlatform() === 'android'`) and only surface it on Web. Ship the app as free-only for the Android launch, then reintroduce billing after review.

## 🧪 Tests

- [x] **PASS** — Backend test suite: 156/156 pass (12 billing, 6 sprint6, 138 others)
- [x] **PASS** — New tests added for `DELETE /api/auth/me` (see `backend/tests/test_delete_account.py`)
- [ ] **WARN** — Device testing on physical Android hardware — required before Play Console submission

## 📚 Docs

- [x] **PASS** — `docs/GOOGLE_PLAY_RELEASE.md`
- [x] **PASS** — `docs/GOOGLE_PLAY_CHECKLIST.md` (this file)
- [x] **PASS** — `docs/google-play-data-safety.md`
