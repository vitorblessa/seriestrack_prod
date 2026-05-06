# Auth Testing Playbook for SeriesTrack

## App auth model
- Backend issues JWT access_token via `/api/auth/login`, `/api/auth/register`, and `/api/auth/google` (Emergent Google OAuth callback exchange).
- Frontend stores the JWT in localStorage (key: `seriestrack_token`) and sends it as `Authorization: Bearer <token>` on all protected calls.
- Users are stored in `users` collection. For Emergent Google auth, users are upserted by email; existing email/password users are linked (no duplicate created). New Google-only users have NO password_hash.

## Test credentials
- Admin (email/pass): `admin@seriestrack.app` / `Admin@123` (seeded on backend startup)
- Google OAuth flow: open `/login`, click "Continuar com Google" — redirects to `https://auth.emergentagent.com`, returns to `${origin}/auth/callback#session_id=…`, frontend POSTs `{ session_id }` to `/api/auth/google`, backend exchanges with `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data`, returns `{ user, access_token }`.

## Endpoints to verify
- `POST /api/auth/google` { session_id } → 200 with `{ user, access_token }` on valid session_id; 401 on invalid.
- `GET /api/auth/me` with `Authorization: Bearer <token>` → 200 user.
- All previously-tested endpoints continue to work.

## Browser test for Google flow
1. Navigate to `${REACT_APP_BACKEND_URL}/login`.
2. Click button with `data-testid="google-login-button"`.
3. Verify redirect to `auth.emergentagent.com`.
4. (Manual) Complete Google flow, verify return to `${origin}/auth/callback#session_id=...`.
5. Verify `/dashboard` loads, user data populated, localStorage has `seriestrack_token`.

## DB verification (mongosh)
```
use seriestrack
db.users.find({}).pretty()
db.users.find({password_hash: {$exists: false}}).pretty()  # google-only users
```

## Notes
- We don't store the Emergent `session_token`; we issue our own JWT, so OAuth users don't have a different cookie/token.
- OAuth flow requires real browser interaction — pure curl tests cannot complete the Google step. Backend `/api/auth/google` can be tested by mocking session_id.
