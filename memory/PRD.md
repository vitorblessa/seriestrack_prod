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

## P1 backlog
- [ ] Schedule daily cron worker that calls `notify_today` for all users automatically.
- [ ] Cache TMDB responses (5-min in-memory) to reduce API calls on hot endpoints.
- [ ] Auto-expand season 1 on first load (small UX papercut flagged in tests).
- [ ] Apple OAuth (iOS users); confirm/email reset flow.
- [ ] Friend follow + activity feed (full social, currently MVP).
- [ ] Migrate FastAPI startup/shutdown to lifespan context.
- [ ] Split server.py (954 lines) into routers per domain.

## P2 backlog
- [ ] Premium tier (remove ads, advanced alerts, Plex/Jellyfin, statistics export).
- [ ] React Native + Expo mobile app (separate project).
- [ ] Recommendations engine (collaborative filter using ratings).
- [ ] Rate limiting on POST /api/reviews and /api/progress.

## Test credentials
See `/app/memory/test_credentials.md`.
