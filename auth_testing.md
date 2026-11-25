# Auth Testing Playbook for SeriesTrack

## App auth model
- Backend issues JWT access_token via `/api/auth/login`, `/api/auth/register`, and `/api/auth/google` (Google ID-token verification).
- Frontend stores the JWT in localStorage (key: `seriestrack_token`) and sends it as `Authorization: Bearer <token>` on all protected calls.
- Users are stored in `users` collection. For Google sign-in, users are upserted by email; existing email/password users are linked (no duplicate created). New Google-only users have NO password_hash.

## Test credentials
- Admin (email/pass): `admin@seriestrack.app` / `Admin@123` (seeded on backend startup)
- Google sign-in flow: open `/login`, click "Continuar com Google" — Google Identity Services (web) or the native account picker (Android) returns an ID token, the frontend POSTs it to `/api/auth/google`, the backend verifies it against `GOOGLE_CLIENT_ID` and returns `{ user, access_token }`.

## Endpoints to verify
- `POST /api/auth/google` { credential } (Google ID token) → 200 with `{ user, access_token }` on a valid token; 401 on invalid.
- `GET /api/auth/me` with `Authorization: Bearer <token>` → 200 user.
- All previously-tested endpoints continue to work.

## Browser test for Google flow
1. Navigate to `${REACT_APP_BACKEND_URL}/login`.
2. Click button with `data-testid="google-login-button"`.
3. (Manual) Complete the Google account picker / One Tap prompt.
4. Verify the app navigates to `/dashboard`.
5. Verify `/dashboard` loads, user data populated, localStorage has `seriestrack_token`.

## DB verification (mongosh)
```
use seriestrack
db.users.find({}).pretty()
db.users.find({password_hash: {$exists: false}}).pretty()  # google-only users
```

## Notes
- We don't store Google's ID token; we issue our own JWT, so OAuth users don't have a different cookie/token.
- OAuth flow requires real browser interaction — pure curl tests cannot complete the Google step. Backend `/api/auth/google` can be tested by mocking the Google token verification.
