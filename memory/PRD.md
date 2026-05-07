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

## P1 backlog (post Sprint-2)
- [ ] Cache TMDB /tv/{id} (15-30min LRU) — big perf win on /streaming/episodes + /stats/advanced.
- [ ] Cache AI recommendations per user (5-10min TTL) — deterministic given inputs, costs $$ otherwise.
- [ ] Trial period of 14 days (requires expiration cron).
- [ ] Wrapped 2026 page (year-end viral feature).
- [ ] Stripe Customer Portal for self-cancel.
- [ ] Split server.py (1624 lines) into routers (auth, library, streaming, billing, pro).
- [ ] Daily cron worker for notify_today + push.
- [ ] Apple OAuth (iOS users), email reset flow.
- [ ] Friend follow + activity feed (full social).
- [ ] Migrate FastAPI startup/shutdown to lifespan context.

## P2 backlog
- [ ] Premium tier (remove ads, advanced alerts, Plex/Jellyfin, statistics export).
- [ ] React Native + Expo mobile app (separate project).
- [ ] Recommendations engine (collaborative filter using ratings).
- [ ] Rate limiting on POST /api/reviews and /api/progress.

## Test credentials
See `/app/memory/test_credentials.md`.
