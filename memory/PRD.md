# SeriesTrack — PRD

## Original problem statement
Crie um aplicativo moderno chamado SeriesTrack, focado em acompanhar automaticamente o lançamento de episódios de séries em múltiplos streamings. Visual futurista, dark mode elegante, UI estilo Netflix/Letterboxd/IMDb/TV Time. Aparência de startup unicórnio com UX fluida e foco em retenção.

## User decision (asked twice)
- Plano padrão: web app completo (FastAPI + MongoDB + React), JWT email/password auth, TMDB API real (token fornecido pelo usuário), calendário e notificações in-app, sem features sociais no MVP.

## Architecture
- **Backend** (FastAPI + Motor + httpx + bcrypt + PyJWT) — single file `/app/backend/server.py`, all routes prefixed `/api`.
- **Auth** — JWT Bearer in `Authorization` header, token stored in `localStorage` (`seriestrack_token`). `httpOnly` cookies also set as a fallback.
- **TMDB integration** — proxied through `/api/series/*` endpoints with Bearer Read-Token; region BR, language pt-BR.
- **Database** — MongoDB collections: `users`, `library`, `notifications`. Indexes on `users.email` (unique), `library (user_id, tmdb_id)` (unique).
- **Frontend** — React + Tailwind + shadcn/ui (Tabs, Sonner toaster). Routes: `/`, `/login`, `/register`, `/dashboard`, `/search`, `/series/:id`, `/library`, `/calendar`, `/notifications`, `/profile`. AuthProvider w/ ProtectedRoute.
- **Design** — Obsidian black `#0A0A0C` + Electric Coral `#FF2A54` accent. Fonts: Cabinet Grotesk + Outfit. Glass surfaces, poster hover lifts, snap-x rails.

## Implemented (Feb 2026)
1. JWT auth (register/login/logout/me) + admin seed.
2. TMDB endpoints: trending, popular, top_rated, airing_today, on_the_air, search, detail (with watch providers BR + cast + recommendations + seasons), season detail with episodes.
3. Library CRUD with status (watching/paused/finished/want), upsert by `(user_id, tmdb_id)`.
4. Calendar/Upcoming endpoint (parallel-ish per library item) returning next + last episode per show with provider names.
5. Notifications feed (created on library add) + unread count + mark all read.
6. Stats endpoint (counts by status).
7. UI: Splash hero, Login/Register split layout, Dashboard with featured hero + 5 rails + upcoming grid, Search w/ debounced TMDB search, Series Detail w/ hero + actions + seasons tabs + cast + recommendations, Library w/ tabs + stats + remove, Calendar w/ month grid + per-platform filter chips + list view, Notifications, Profile with stats.

## Phase 2 Implemented (Feb 2026)
8. **Episode tracking** — POST/GET /api/progress + summary; per-season + overall progress bars on series detail; episode toggle button per episode.
9. **Reviews & Ratings** — POST/GET/DELETE /api/reviews; 1–5 star widget + comment; community feed shown on series detail; average + count.
10. **Public profile + Share list** — GET /api/users/{id}/public + /library; /u/:id route shows public profile (stats, recent reviews, library); MyLibrary "Compartilhar minha lista" button copies link.
11. **Google OAuth via Emergent Auth** — POST /api/auth/google (session_id → JWT); /auth/callback page; "Continuar com Google" button on login/register.
12. **Web Push notifications** — VAPID keys configured; /api/push/{public_key, subscribe, test, notify_today}; service worker handles push + notification clicks; Settings page UI to enable/disable + send test + trigger today's check.
13. **PWA installable + offline** — manifest.json (start_url=/dashboard, theme #0A0A0C), service worker with network-first navigations + cache-first static.

## Tested
- Iteration 1: 18/18 pytest + e2e Playwright — all green.
- Iteration 2: 42/42 pytest (24 new + 18 regression) + e2e Playwright on all phase-2 flows — all green.

## Sprint 1 — Pro monetization (Stripe Checkout via emergentintegrations)
14. **Plans backend**: PRO_PLANS dict (pro_monthly R$ 12,90/30d, pro_yearly R$ 99,00/365d) — server-side fixed; frontend never sets price.
15. **Endpoints**: `GET /api/billing/plans`, `POST /api/billing/checkout`, `GET /api/billing/status/{session_id}` (idempotent credit), `GET /api/billing/me`, `POST /api/webhook/stripe` (signature-verified).
16. **`payment_transactions` collection** with session_id (unique), credited flag for idempotency.
17. **`is_pro()` + `require_pro` deps**: ready for gating Pro features.
18. **`_credit_pro()`** extends subscription_renews_at by N days from max(now, current_renews) — supports stacking renewals.
19. **Frontend**: `/pricing` (public) with Free vs Pro side-by-side, monthly/yearly toggle (-36% badge), Stripe redirect on click; `/billing/success` with status polling (12 retries × 2.5s).
20. **UI integration**: nav-upgrade-btn in header (free users), nav-pro-badge (Pro users); profile-upgrade-link / profile-pro-badge on /profile.

## Sprint 2 — Pro feature gating + AI + advanced stats (Feb 2026)
21. **Library cap (50)**: free-tier users are 402-blocked from adding the 51st series; UPDATE of existing series still works; Pro = unlimited. New `GET /api/limits` returns current usage.
22. **AI Recommendations** (`POST /api/ai/recommendations`, `require_pro`): Claude Sonnet 4.5 via Emergent Universal Key analyzes user's library + reviews, returns 5 series with personalized "porque você vai gostar" explanation in pt-BR. Output is enriched with TMDB posters + in_library flag.
23. **Advanced stats** (`GET /api/stats/advanced`, `require_pro`): total eps watched, estimated hours/days, top series, top genres (parallel TMDB fetches), 365-day heatmap, library breakdown, top months.
24. **Frontend pages**: `/ai-recommendations` (with paywall fallback for free), `/stats` (with paywall fallback). Both have nav links visible to all users — Free clicks open paywall.
25. **402 cap UX**: SeriesDetail action buttons show toast with "Fazer upgrade" action button when free user hits cap.

## Tested
- Iteration 6: 18/18 Sprint-2 backend tests + 100% frontend e2e (Pro + Free flows). Zero bugs.

## Sprint 3 — Upsell + Conveniência (Feb 2026)
26. **Free-tier upsell hook on Dashboard** (`GET /api/ai/preview_rec`, no LLM cost): returns ONE TMDB-native recommendation seeded by user's most-recent library item. Frontend component `UpsellPreview.jsx` shows poster + title + 4 locked teaser slots + CTA "Ver mais 4 no Pro" → `/pricing`. Renders only when `subscription_tier !== 'pro'` AND library has items.
27. **Import Trakt** (`POST /api/import/trakt`, multipart): accepts Trakt JSON (list OR `{shows:[]}` wrapped) + CSV (Title/Year/Tmdb columns). Resolves each entry via TMDB (uses provided tmdb_id when present, falls back to title+year search). Inserts as `want`. Free-tier 50-cap enforced — overflow goes to `skipped_cap`. 5MB / 300-item hard limits; semaphore-throttled to 8 concurrent TMDB calls.
28. **Export iCal** (`GET /api/calendar/ical`): returns RFC-5545 compliant `text/calendar` feed of `next_episode_to_air` + `last_episode_to_air` for every show in the library. Accepts both `Authorization: Bearer` AND `?token=<jwt>` query param so Google Calendar / Apple Calendar / Outlook can subscribe by URL. Settings page exposes "Baixar .ics" + "Copiar URL de assinatura".

## Tested
- Iteration 7: 17/17 backend tests (preview_rec 4, import_trakt 7, ical 5, fixtures 1) + Playwright e2e on Free upsell + Admin settings Trakt upload (real file → "✓ 2 séries adicionadas") + iCal download (real file with suggested_filename `seriestrack.ics`). Zero bugs.

## Sprint 3.5 — Backlog burn-down / Health refactor (Feb 2026)
29. **TMDB cache (in-process)**: `tmdb_get_tv()` helper caches `/tv/{id}` responses for 30 min — used by `/calendar/upcoming`, `/calendar/ical`, `/push/notify_today`, `/streaming/episodes`, `/library` upsert, `/progress/summary`, `/stats/advanced`, `/import/trakt`. Auto-evicts oldest 500 when cache exceeds 2000 entries.
30. **AI recs cache (per user)**: `/ai/recommendations` results cached for 10min keyed by `(user_id, lib+reviews signature)` — invalidates automatically when library/ratings change. Response includes `cached: true|false` flag.
31. **iCal status filter**: `/calendar/ical` now only fetches shows in `status in ('watching','want')` — drops TMDB fetches for finished/paused entries (big win for large Pro libraries).
32. **Scoped iCal feed token**: NEW endpoints `POST /api/calendar/ical/feed` (mint long-lived 365d read-only JWT) + `DELETE /api/calendar/ical/feed` (revoke all by bumping `calendar_feed_version`). The `?token=` query param on `/calendar/ical` now **rejects** access tokens — only accepts scoped feed tokens. Leaked feed URL can't escalate to account access.
33. **server.py refactor**: split from 2078 lines → 60 lines. New layout:
    - `core/config.py` — env vars + constants
    - `core/db.py` — Mongo client
    - `core/security.py` — JWT, hashing, auth deps, serialize_user, is_pro/require_pro
    - `core/tmdb.py` — TMDB client + tmdb_get_tv cache + normalize_show
    - `core/models.py` — all Pydantic request models
    - `routes/auth.py` — register/login/logout/me/google
    - `routes/series.py` — TMDB proxy routes
    - `routes/library.py` — library + progress + reviews + public profile + stats + limits
    - `routes/calendar_routes.py` — /calendar/upcoming + iCal mint/revoke/feed + notifications
    - `routes/push.py` — Web Push (VAPID)
    - `routes/streaming.py` — streaming-platform discovery
    - `routes/billing.py` — Stripe Checkout + webhook
    - `routes/ai.py` — preview rec + Claude AI recommendations + advanced stats
    - `routes/imports.py` — Trakt CSV/JSON import
34. **Frontend Settings iCal UX**: "Gerar URL de assinatura" button now mints scoped token via `POST /calendar/ical/feed`, displays the URL with a "Revogar" button. Security copy updated.

## Tested
- Iteration 7.5: 103/103 pytest pass (full suite including phase2, phase3, phase4 streaming, billing, sprint2 pro, iter7 new features + 2 pre-existing test expectations corrected to match production sub-channel-rejection logic). Backend smoke-tested 12 endpoints (all 200). Frontend e2e Settings page renders cleanly. Zero new regressions from refactor.

## Sprint 4 — Temas Pro + Wrapped (Feb 2026)
35. **UI Themes (Pro)**: 9 temas — `default` (Free) + 8 Pro (`oled`, `netflix`, `disney_plus`, `hbo_max`, `prime_video`, `apple_tv`, `paramount_plus`, `globoplay`). Cada um troca background, CSS vars de accent e gradient do `.btn-primary`. Implementação via `body[data-theme="X"]` em `themes.css`.
    - `GET /api/me/preferences` → tema atual + lista de free/pro themes + tier.
    - `PATCH /api/me/preferences` com `{ui_theme}` — 402 com `code='pro_theme_required'` se Free escolher Pro theme. 400 se tema desconhecido.
    - Frontend: `ThemeProvider` em `/app/frontend/src/lib/theme.jsx` aplica `data-theme` no `<body>` e sincroniza com backend on mount + on change. Settings tem grid 4×3 com swatches preview + lock icon.
36. **Wrapped 2026**: Year-in-review estilo Spotify Wrapped.
    - `GET /api/wrapped/{year}` (auth required) → `{totals, top_series, top_genres, top_day_of_week, top_month, longest_streak_days, biggest_binge, first_episode, last_episode, reviews}`. Calcula a partir de `progress.watched_at` + `library` + `reviews`.
    - `GET /api/wrapped/{year}/share/{user_id}` — PÚBLICO (sem auth) pra link compartilhável.
    - Frontend `/wrapped`, `/wrapped/{year}`, `/wrapped/share/{userId}/{year}` (esta sem auth). Animações fade-up staggered. Botão "Compartilhar" copia link ou usa `navigator.share()` mobile. Share view tem header minimal com CTA "Criar meu Wrapped" → `/register` pra signups orgânicos.

## Tested
- Iteration 8: 20/20 backend pytest pass (theme listing + 402 pro-gating + admin all themes + 400 unknown + wrapped shape + empty/year-bounds + public share). Frontend: 13/13 após fix do bug de Share URL no owner view (data?.user?.id || authUser?.id fallback). Clipboard verified via Playwright: `https://show-notify.preview.emergentagent.com/wrapped/share/{userId}/2026`.

## P1 backlog (post Sprint-4)
- [ ] Custom private lists (Pro: ilimitado, Free: 1) — pendente do Sprint 3.
- [ ] Wrapped: cachear genres top-10 por tmdb_id em mongo (evita TMDB fetch a cada request).
- [ ] Wrapped: implementar `top_streaming` (atualmente retorna array vazio — `tmdb_get_tv` não traz watch/providers).
- [ ] Trial period de 14 dias (cron de expiração).
- [ ] Stripe Customer Portal pra self-cancel.
- [ ] Daily cron worker pra notify_today + push.
- [ ] Apple OAuth (iOS users), email reset flow.
- [ ] Migrar `app.on_event` → `lifespan` (FastAPI deprecation warning).
- [ ] Friend follow + activity feed (full social).
- [ ] Migrate FastAPI startup/shutdown to lifespan context.

## P2 backlog
- [ ] Premium tier (remove ads, advanced alerts, Plex/Jellyfin, statistics export).
- [ ] React Native + Expo mobile app (separate project).
- [ ] Recommendations engine (collaborative filter using ratings).
- [ ] Rate limiting on POST /api/reviews and /api/progress.

## Test credentials
See `/app/memory/test_credentials.md`.
