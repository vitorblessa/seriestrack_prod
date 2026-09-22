# Google Play — Data Safety Declaration

Fill this into the Play Console → **Data safety** form. Each table row maps to a question Google asks.

## Data collected

| Data type | Category | Collected? | Shared? | Ephemeral? | Optional? | Purpose |
| --- | --- | --- | --- | --- | --- | --- |
| Name | Personal info | ✅ | ❌ | ❌ | ❌ | Account management, profile |
| Email address | Personal info | ✅ | ✅ (Stripe for billing only) | ❌ | ❌ | Account creation, notifications, billing |
| User IDs | Personal info | ✅ (internal ID) | ❌ | ❌ | ❌ | Session, associate library/progress |
| Photos | Photos & videos | ✅ (Google profile picture only, if logged in with Google) | ❌ | ❌ | ✅ | Display avatar in profile |
| App interactions | App activity | ✅ | ❌ | ❌ | ❌ | Track watched episodes, ratings |
| In-app search history | App activity | ❌ | — | — | — | Not stored |
| Other user-generated content | App activity | ✅ (reviews, ratings, custom lists) | ❌ (public reviews visible to other users of the app) | ❌ | ✅ | Feature: user reviews |
| Crash logs | App info & performance | ❌ (no crash reporter integrated yet) | — | — | — | — |
| Diagnostics | App info & performance | ✅ (server-side logs: IP, user agent) | ❌ | ❌ | ❌ | Security, abuse prevention |
| Device or other IDs | Device or other IDs | ❌ | — | — | — | Not collected |
| Approximate location | Location | ❌ | — | — | — | Not collected |
| Precise location | Location | ❌ | — | — | — | Not collected |
| Purchase history | Financial info | ✅ (Stripe transaction IDs, amount, currency, status) | ✅ (Stripe processes payments) | ❌ | ✅ | Pro subscription |
| Credit card & payment info | Financial info | ❌ (handled entirely by Stripe, never touches our servers) | — | — | — | — |
| Contacts | Contacts | ❌ | — | — | — | — |
| Files & docs | Files & docs | ❌ | — | — | — | — |
| Calendar events | Calendar | ❌ (we generate iCal *export*, we don't read the user's calendar) | — | — | — | — |
| Microphone / audio | Audio | ❌ | — | — | — | — |
| Camera / images | Photos & videos | ❌ | — | — | — | — |
| Health & fitness | Health & fitness | ❌ | — | — | — | — |
| Messages | Messages | ❌ | — | — | — | — |
| Web browsing history | Web browsing | ❌ | — | — | — | — |

## Security practices

| Question | Answer |
| --- | --- |
| Is data encrypted in transit? | ✅ Yes — all traffic uses HTTPS/TLS 1.3. `usesCleartextTraffic="false"` in the manifest, Network Security Config denies cleartext. |
| Can users request data deletion? | ✅ Yes — in-app at Settings → "Excluir minha conta" and public URL `/delete-account`. |
| Do you follow Play's Families Policy? | Not applicable — target audience 13+, not directed at children. |
| Independently validated against a global security standard? | ❌ Not yet. |

## Data deletion URL

`https://show-notify.emergent.host/delete-account`

- Requires user authentication.
- Immediately purges: user profile, library, watched-episode progress, reviews, notifications, push subscriptions, preferences, custom lists, AI recommendation cache.
- Stripe subscription is cancelled at end of period.
- Payment transaction records are anonymized (user_id → `deleted-<id>`) and retained 5 years per Brazilian tax law.
- No downtime, no support ticket required.

## Third parties receiving data

1. **Stripe** — email + purchase history + billing address (if user provides). Purpose: subscription processing. Region: US. Privacy policy: https://stripe.com/privacy
2. **Google** (only if user chooses "Sign in with Google") — name, email, avatar URL. Purpose: authentication. Privacy: https://policies.google.com/privacy
3. **TMDB** — no user data is sent; we only *pull* series metadata.
4. **Emergent** — hosts backend + database. Bound by MSA/DPA. Not a data controller.

## Retention

| Data | Retention |
| --- | --- |
| Profile, library, progress, reviews | Until account deletion |
| Session tokens | 24h (access) / 30d (refresh) |
| Payment transactions | 5 years (Brazilian tax law), user_id anonymized on deletion |
| Server logs | 90 days rolling |
