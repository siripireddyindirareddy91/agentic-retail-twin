# SUPPLYTWIN AI

**An Agentic AI-Based Digital Twin Framework for Real-Time Retail Supply Chain Disruption Management**

Intelligent Supply Chain. Predictive Decisions. Autonomous Recovery.

## Live frontend

https://supplytwin-ai.vercel.app

The production deployment now includes FastAPI serverless functions and a persistent Neon PostgreSQL database. **Create an account**, then sign out and sign in using that account. New registrations receive the Analyst role. Synthetic operational data is shared in the demonstration workspace. No real logistics integrations are connected.

The full local application uses React → FastAPI → SQLAlchemy → SQLite. Production uses the same backend with PostgreSQL. The optional browser sandbox is disabled by default and requires `VITE_SANDBOX=true`; it remains a separate dataset without cloud authentication.

## Run locally

Prerequisites: Node 20.19+ or 22.12+, Python 3.12.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.services.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to http://127.0.0.1:8000. Swagger: http://127.0.0.1:8000/docs. OpenAPI: http://127.0.0.1:8000/openapi.json.

Development demo accounts (shown in the UI only in development):

| Role | Email | Default local password |
| --- | --- | --- |
| Admin | admin@supplytwin.demo | SupplyTwin@2026 |
| Analyst | analyst@supplytwin.demo | SupplyTwin@2026 |

Set `DEMO_PASSWORD` **before first seeding** to override these passwords. It does not rotate existing accounts. Public cloud deployments must use a private, strong demo password or disable demo mode and provision accounts explicitly. Registration always grants Analyst; it never accepts a client-supplied role.

## Modules

17 routes: Overview, Digital Twin, Live Control Tower, Supply Chain Network, Inventory, Warehouses, Suppliers, Shipments, Disruptions, AI Agents, Simulator, Risk Analytics, Recovery, Orders, Reports, Notifications, Settings.

Implemented operations include authenticated API access, role checks, inventory CRUD and stock history, node CRUD and route connections, order creation and status changes, shipment details and timeline, disruption creation and risk scoring, deterministic scenario evaluation, persisted simulation history, LangGraph workflow execution, human approval/rejection/editing, transactional simulated recovery, CSV/PDF exports, notification read state, profile editing, audit history, and controlled synthetic event generation.

## Demonstration

1. Log into the local application, or open the deployed browser sandbox.
2. Explore **Digital Twin** and click a supplier or warehouse.
3. Open **Scenario Simulator**, select Supplier Failure, an affected supplier, duration, and severity.
4. Run the simulation. Compare available inventory, exposed orders, risk, financial impact, and four recovery strategies.
5. Inspect **AI Agent Center**. Backend orchestration uses LangGraph; the standalone browser uses equivalent deterministic rules without Python.
6. Open **Recovery Planner**, approve the new plan, then explicitly execute the simulation.
7. Inspect updated inventory, cleared shipment delays, order risk, resolved disruption, notification, and audit records.
8. Export recovery data from **Reports & Analytics**.

## Verification

```powershell
cd backend
python -m pytest app/tests -q -p no:cacheprovider
cd ../frontend
npm run build
```

Updated verification on 2026-11-05: **13 backend tests passed**. Production TypeScript/Vite build passed. Live PostgreSQL checks passed for registration, duplicate rejection, wrong-password rejection, login, all principal read APIs, logout/token revocation, and fresh login retaining the same account. Earlier sandbox simulation/approval/execution verification also passed. Production FastAPI now runs on Vercel. Exhaustive mobile/browser coverage remains unverified.

## Source layout

```text
frontend/
  src/App.tsx          Layout, 17 routed interfaces, shared UI components
  src/styles.css      Navy/blue/teal design system and responsive layouts
  src/api.ts          Authenticated API client and report downloads
  src/sandbox.ts      Explicit IndexedDB demo adapter
  src/main.tsx        React Router and TanStack Query providers
  vercel.json         Vite build and SPA routing
backend/
  app/main.py         FastAPI endpoints, request validation, authorization
  app/core/           SQLAlchemy sessions and security
  app/models/         Relational ORM schema
  app/services/       Deterministic seed, simulation and recovery
  app/agents/         LangGraph workflow
  app/ml/             Offline training and evaluation utility
  app/tests/          Integration tests
  alembic/            Initial schema migration
  Dockerfile
docs/
  ARCHITECTURE.md
  DEPLOYMENT.md
  TESTING.md
render.yaml
docker-compose.yml
```

## Known limits

- This is a working demonstration platform, not a production-certified enterprise system or a completion of every item in the expansive master brief.
- Production now uses a Vercel-hosted FastAPI function and Neon PostgreSQL. Neon and Vercel free-tier quotas and cold starts still apply. Render configuration is retained as an alternative hosting option.
- Scenario types currently share a generic exposure model parameterized by node, duration, and severity; there are no validated disaster, fuel, road-routing, or demand-elasticity models.
- Simulated execution replenishes low stock and clears delays; it does not optimize donor stock transfers, reserve physical stock, contact suppliers, or execute real procurement.
- Agents are deterministic specialized workflow stages. No LLM provider is called. Environment placeholders are provided, but an LLM connector is not implemented. Heuristic confidence is not a calibrated probability.
- Machine learning training/evaluation utilities are included but no models have been trained or activated. No accuracy claims are made.
- Password reset tokens are displayed only to loopback/test clients in demo mode. SMTP email delivery is not configured. Hosted password reset needs an email integration.
- Notifications are workspace-wide. There is one workspace, no tenant isolation, no fine-grained ownership, and no invitation/role administration interface.
- Event simulation is client-controlled polling, not a durable background worker or WebSocket service. It pauses when the control tower is unmounted.
- Browser sandbox PDF export uses browser print. FastAPI generates actual downloadable PDFs; report layouts are utilitarian.
- Schema uses typed network nodes for suppliers/warehouses/distribution/stores rather than four redundant subtype tables. Simulation results and impacts are JSON fields instead of separate result/impact tables.
- Some advanced filters, detailed supplier delay analysis, product editing/deletion, geospatial route maps, and complete order item editing remain outside this initial implementation.
- Automated integration tests use isolated SQLite; live registration, login, and persistence are separately checked against production PostgreSQL using a disposable test account.

See [Deployment](docs/DEPLOYMENT.md), [Architecture](docs/ARCHITECTURE.md), and [Testing](docs/TESTING.md).
