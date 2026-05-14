# amaca frontend

SvelteKit + Vite SPA for the amaca backend.

## Dev

```sh
npm install
npm run dev               # listens on http://localhost:5173, proxies /api → :8000
```

The Vite dev server proxies `/api/*` (including WebSocket upgrades) to the
FastAPI backend at `localhost:8000`. The backend must already be running:

```sh
# in another terminal
source ~/.venvs/amaca-dev/bin/activate
uvicorn amaca.api.app:app --reload
```

### Local auth without GitHub OAuth

Set `AMACA_DEV_LOGIN=1` on the backend to enable a dev-only `/api/auth/dev-login`
endpoint that authenticates any username without going through GitHub.
The login page surfaces a dev-login form when it sees this endpoint.
Do **not** enable this in production.

### Real GitHub OAuth (for production-ish dev)

Register an OAuth App on GitHub with callback URL
`http://localhost:5173/api/auth/callback` (so the cookie ends up on the
SPA origin via the Vite proxy), then set on the backend:

```sh
export AMACA_GITHUB_CLIENT_ID=...
export AMACA_GITHUB_CLIENT_SECRET=...
export AMACA_OAUTH_REDIRECT_URI=http://localhost:5173/api/auth/callback
export AMACA_ALLOWED_GITHUB_USERS=your-handle
export AMACA_ADMIN_GITHUB_USERS=your-handle
export AMACA_SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

## Build

```sh
npm run build             # outputs to ./build/
```

Built site is a static SPA (`adapter-static`). FastAPI will serve it
from `/` in production (mount comes in a follow-up commit).
