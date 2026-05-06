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

## Tested
- 18/18 pytest backend tests pass.
- Frontend e2e via Playwright: splash, register, login, dashboard rails, search, series detail (all 4 actions + season tab), library tabs + remove, calendar grid + filters, notifications, profile + logout — all green.

## P1 backlog (next iterations)
- [ ] Update flow: status change shouldn't always create a notification (dedupe).
- [ ] Calendar: parallelize TMDB calls with `asyncio.gather` for big libraries.
- [ ] Episode "watched" tracking with progress bars per season.
- [ ] Real push notifications (web-push or email via Resend).
- [ ] Recommendations based on user's library (collaborative filter).
- [ ] Wrap `ObjectId(...)` in try/except → 401 instead of 500 on malformed sub.
- [ ] Migrate `@app.on_event` to FastAPI lifespan context.

## P2 backlog
- [ ] Social features (follow friends, share lists, ratings, comments).
- [ ] Premium tier (remove ads, advanced alerts, Plex/Jellyfin integration, statistics export).
- [ ] OAuth providers (Google / Apple).
- [ ] Mobile app (React Native + Expo).
- [ ] Offline mode (PWA + IndexedDB).

## Test credentials
See `/app/memory/test_credentials.md`.
