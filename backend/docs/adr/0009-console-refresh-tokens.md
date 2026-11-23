# ADR 0009: Console Refresh Tokens

## Status
Accepted.

## Date
2026-11-23

## Context
The console signed in with one JWT (`ACCESS_TOKEN_EXPIRE_MINUTES`, 60 in the example env) kept in the tab's `sessionStorage`. When it expired, the next request answered 401 and the user was sent back to the login page mid-task. Signing out only forgot the token in the browser: the server had no record of it, so a copied token stayed valid until it expired. A longer lifetime would make both worse. API keys (`/mcp`) are a separate credential and are not affected.

## Decision
1. **Two tokens.** Login returns a short-lived access token (the same stateless JWT, now 15 minutes in the example env) in the body, and sets an opaque refresh token (`mhr_` + 256 random bits) as a cookie. `POST /auth/refresh` exchanges the cookie for a new access token. REST endpoints and `get_current_principal` still accept only the access token; the refresh token is never a bearer token, and API keys are unchanged.
2. **The refresh token is an httpOnly cookie** (`mcp_hub_refresh`), `Path=/api/v1/auth`, `Max-Age` = `REFRESH_TOKEN_EXPIRE_DAYS`, with `Secure` and `SameSite` from `REFRESH_COOKIE_SECURE` and `REFRESH_COOKIE_SAMESITE` (`strict` in the example env; `none`, which needs `Secure`, only when console and API are on different sites). Scripts in the page cannot read it, so an XSS cannot carry it off. The console sends it with `withCredentials` on login, refresh and logout only.
3. **CSRF check.** `/auth/refresh` and `/auth/logout` act on the cookie, so they also require `X-MCP-Hub-Client: console` (403 otherwise). A cross-site page cannot add a custom header without a CORS preflight, and only `CORS_ORIGINS` pass one. A forged refresh could not read the new token anyway; the header mainly stops forced logouts.
4. **Stored hashed, grouped by sign-in.** `console_refresh_tokens` keeps the SHA-256 of each token with `user_id` (cascade delete), `family_id`, `expires_at`, `used_at` and `revoked_at`. Each login starts a family; it is the unit that logout and reuse detection revoke, so other sign-ins of the same account (another browser) are untouched.
5. **Rotation on every refresh.** One transaction marks the presented token used, with a conditional `UPDATE ... WHERE used_at IS NULL AND revoked_at IS NULL AND expires_at > now`, and stores its successor in the same family. Of two concurrent rotations of one token only one matches. Rotation and family revocation both take a per-family advisory lock (`pg_advisory_xact_lock`), so a logout running alongside a refresh either stops it or also revokes the successor it wrote; without the lock the revoke's `UPDATE` would not see the row being inserted. The successor gets a fresh `REFRESH_TOKEN_EXPIRE_DAYS` (sliding expiry): a console used at least once in that period stays signed in.
6. **Reuse revokes the family.** Presenting a token that was already used means two parties hold it: an attacker who copied it, or a client that lost the response. The hub cannot tell them apart, so it revokes the whole family and answers 401; the user logs in again. An expired or revoked token is a plain 401.
7. **Logout** (`POST /auth/logout`) revokes the cookie's family and clears the cookie. It needs no valid access token and always answers 204, so a stale console can always sign out. Access tokens already issued stay valid until they expire (at most `ACCESS_TOKEN_EXPIRE_MINUTES`).
8. **The console refreshes on 401 and retries once.** The Axios response interceptor (`src/lib/api-client.ts`) catches a 401 from a protected endpoint, calls `refreshSession()` and repeats the request once with the new token; a second 401, or a failed refresh, signs out as before. Requests failing together share one in-flight refresh, and a request whose 401 arrives after another refresh already finished reuses that token. A tab that opens with no access token (a new tab, a reopened browser) tries the cookie in `AuthGuard` before showing the login page; a token that goes away later (sign-out) goes straight to login, since a refresh then would race the logout request.
9. **Tabs refresh one at a time.** Tabs share the cookie but keep their own access token in `sessionStorage`. Two tabs refreshing at once would present the same token twice and trip rule 6. `refreshSession()` holds the Web Lock `mcp-hub-refresh`, so the second tab waits and then sends the cookie the first one set.
10. **Expired rows are deleted** by the hourly `purge-expired-refresh-tokens` job (`AuthService.purge_expired_refresh_tokens`, one idempotent `DELETE`, safe on several instances).

Code: `app/services/auth_service.py` (`login`, `refresh`, `logout`), `app/infrastructure/repositories/refresh_token_repository.py`, `app/api/v1/auth_router.py`, `require_console_client` in `app/api/dependencies.py`, `app/core/constants/auth_constants.py`; console: `src/lib/api-client.ts`, `src/components/layout/AuthGuard.tsx`, `useLogout`.

## Why
- **httpOnly cookie over `sessionStorage`:** the refresh token outlives the access token by days, so it is the one worth protecting from page scripts. The cost is CSRF (rule 3) and the shared-cookie race (rule 9).
- **Opaque and stored, not a second JWT:** rotation, reuse detection and logout all need server-side state; a random token with a stored hash is simpler and cannot be forged with a leaked `JWT_SECRET`.
- **Strict reuse detection over a grace window:** a window that accepts a just-used token for a few seconds would also accept a thief's replay in that window. Serialising refreshes in the console removes the legitimate cause instead.
- **Revoke the family, not the account:** a stolen token from one browser should not sign the owner out everywhere.

## Consequences
- The console now stays signed in across tabs and browser restarts for up to `REFRESH_TOKEN_EXPIRE_DAYS` without use; before, closing the tab signed out.
- A browser without the Web Locks API falls back to the per-tab single flight; two of its tabs refreshing in the same instant sign out (rule 6).
- A refresh whose response is lost (network drop after the server rotated) signs that console out on its next refresh.
- Signing out in one tab ends the sign-in for every tab, but the others notice only when their access token expires.
- New required settings: `REFRESH_TOKEN_EXPIRE_DAYS`, `REFRESH_COOKIE_SECURE`, `REFRESH_COOKIE_SAMESITE`. Deployments behind HTTPS must set `REFRESH_COOKIE_SECURE=true`.
