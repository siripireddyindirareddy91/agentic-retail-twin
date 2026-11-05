# Deployment

## Current production

Application: https://supplytwin-ai.vercel.app

React/Vite frontend and FastAPI Python function run on Vercel in Singapore. Durable accounts and application records live in Neon PostgreSQL on its free plan, connected through the Vercel integration. Registration and login are enabled. New users receive Analyst access to the shared synthetic workspace.

Deploy from the repository root, not frontend/:

```powershell
vercel deploy --prod
```

Root vercel.json builds frontend/ and routes /api/* to api/index.py. Health: /api/health. Swagger: /docs. OpenAPI: /openapi.json.

## Server environment

Configured in Vercel, never committed:

- DATABASE_URL: Neon TLS connection, supplied by the integration.
- JWT_SECRET: generated strong signing key, stable across function instances.
- DEMO_PASSWORD: generated private password for seeded privileged demo accounts.
- DEMO_MODE: true for synthetic data and simulated events.
- CORS_ORIGINS: https://supplytwin-ai.vercel.app
- ACCESS_TOKEN_EXPIRE_MINUTES: 60

Do not enable VITE_SANDBOX on the production project. An empty VITE_API_BASE_URL means same-origin API calls. A separate backend can be selected with a complete VITE_API_BASE_URL at build time.

DEMO_PASSWORD applies only during initial seeding; changing it does not rotate existing passwords. The documented local default password is not used for hosted privileged accounts. Register your own account. Role grants currently require controlled database administration.

Hosted startup requires DATABASE_URL and JWT_SECRET and fails clearly if missing. It never silently substitutes ephemeral SQLite or a per-instance signing key. Local development still supports SQLite.

## Initial setup for another deployment

1. Create PostgreSQL and configure backend environment variables.
2. Run alembic upgrade head from backend/ using that database URL.
3. For synthetic demo data, run python -m app.services.seed with a strong private DEMO_PASSWORD.
4. Deploy from the repository root.
5. Verify API health, registration, sign-out, and sign-in.

Never commit .env.local, .env, .vercel, SQLite files, or signing-key files. The .env.example templates are intentionally included in Git.

## Optional Render backend

render.yaml retains a separate-hosting alternative:

- Root: backend
- Build: pip install -r requirements.txt
- Start: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
- Health: /api/health

Supply database URL, JWT secret, private demo password, and exact CORS origin, then set frontend VITE_API_BASE_URL to the Render URL and rebuild. No Render service is currently required or provisioned.

## Verification and limits

The live API passed registration, duplicate rejection, wrong-password rejection, all principal authenticated read endpoints, logout revocation, and fresh-login persistence. Run backend/smoke_hosted.py from the root with PYTHONPATH=backend and an ignored .env.local to repeat checks using a disposable QA account. It removes only that account afterward.

Free-tier quotas and cold starts apply. Password-reset email delivery still needs SMTP. This remains a single shared workspace with synthetic operations.

Official references: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Vercel deployment](https://vercel.com/docs/cli/deploy), [Marketplace integrations](https://vercel.com/docs/cli/integration).
