# Verification record · 2026-11-05

## Authentication fix verification

- Updated integration suite: **13 passed in 10.24s**, using isolated SQLite configured before application imports.
- Production frontend build passed; frontend defaults to authenticated same-origin API calls.
- Vercel deployment `dpl_AS6EKJsRkXJwY1ZwZZPf7iMjmuhr` returned READY.
- Live `/api/health` returned connected against Neon PostgreSQL.
- Disposable QA account: registration persisted; duplicate rejected; wrong password rejected; login succeeded; auth/me, dashboard, twin network, inventory, warehouses, suppliers, shipments, disruptions, agents, recovery, orders, notifications, and settings returned HTTP 200.
- Logout revoked the old JWT. Fresh login returned the same persisted account ID.
- The smoke script removed only its own disposable account and related audit entries.
- Browser reload showed the real registration form without the sandbox warning.
- Added UTF-8 bcrypt byte-limit tests and batched network/inventory queries. Live dashboard/network reads completed in under a second during the smoke check.

The initial-deployment results below are historical. Their unprovisioned-database limitation was resolved by this fix.

## Passed

- `python -m pytest app/tests -q -p no:cacheprovider`: **11 passed in 11.34s**, one upstream LangGraph pending-deprecation warning.
- `npm run build`: TypeScript compilation and Vite production bundle succeeded. Bundle-size advisory; the app currently uses one large JS bundle.
- Local `GET /api/health`: `{"status":"ok","database":"connected","demo_mode":true,"decision_mode":"Rule-based","ml_trained":false}`.
- Vercel CLI returned production deployment state **READY**, alias **https://supplytwin-ai.vercel.app**.
- Browser verified deployed sandbox renders the overview, 500 orders, 20 suppliers, 18 warehouses, 100 products / 300 stock positions, and network/operational metrics.
- Browser executed Supplier Failure simulation → generated impact and four strategies → approved recommended plan → executed simulation → Executed status and recovery investment updated → overview inventory rose from 367,021 to 367,933 and low-stock positions fell from 64 to 61.

## Backend integration coverage

1. Health, protected access, OpenAPI.
2. Registration, enforced Analyst default, denied management action, logout/session invalidation.
3. All module read endpoints and expected seed counts.
4. Inventory create/update/delete, reserved quantity validation, stock movement history.
5. Supplier CRUD and route connection.
6. Warehouse CRUD and route connection.
7. Order creation/cancellation, shipment status update, disruption creation and risk calculation.
8. Simulation → persisted result → LangGraph logs → blocked unapproved execution → approval → execution → repeat-execution rejection → database stock/shipments/disruption/action/reporting checks.
9. Search filtering, CSV/PDF exports, notification read state.
10. Local demo password reset.
11. Demo reset restores records while preserving accounts.

## Not verified / limits

- No live PostgreSQL database, Docker service, or Render backend was provisioned. Tests used a temporary SQLite database.
- The initial localhost browser preview timed out; deployed browser verification succeeded instead.
- Responsive styles are implemented for mobile/tablet/desktop, but an exhaustive multi-device browser suite was not run.
- Model training, paid LLM inference, email delivery, external GPS, real supply-chain actions, multi-user concurrency/load, and security penetration tests were not performed.
- The standalone sandbox has its own browser implementation. Backend integration tests do not prove parity for every sandbox operation.
