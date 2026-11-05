# Architecture and data model

Production update: root `api/index.py` exposes FastAPI as a Vercel Python function. Neon PostgreSQL stores users and operational records. The frontend defaults to same-origin `/api` calls; sandbox mode requires explicit `VITE_SANDBOX=true`. Hosted startup requires stable `JWT_SECRET` and `DATABASE_URL`. Network aggregate queries are batched rather than issued per node.

## Runtime

React 19 / Vite / TypeScript renders the 17 workspaces. React Router handles navigation; TanStack Query manages server reads and invalidation; Axios adds bearer tokens. Recharts provides operational charts. React Flow renders the directed supply chain graph, with type/risk filtering, route visibility, zoom, node details, and selected-edge highlighting. Framer Motion provides subtle page and modal transitions. Global CSS tokens define the requested palette.

FastAPI validates Pydantic request bodies and exposes OpenAPI. SQLAlchemy persists operational records. SQLite is the zero-credential development default; PostgreSQL via psycopg is the production target. Alembic supplies the initial migration. Foreign keys are enabled for SQLite and declared for PostgreSQL.

## Authentication

Bcrypt password hashes, signed JWTs with expiration, HTTP bearer authentication, server-side session version checks, and version invalidation on logout/reset. New registrations are Analysts. Writers require a management role; plan approval and execution require Admin or Supply Chain Manager. Audit history and demo reset require Admin. CORS origins are explicit. Authentication endpoints have process-local attempt limits. JWT is in browser session storage by default; Remember me opts into local storage. HTTP-only cookie auth and distributed rate limits would be preferable for a hardened deployment.

## Schema

| Table | Primary relationships / purpose |
| --- | --- |
| roles | Role identifiers and labels |
| users | role_id → roles; unique indexed email, password hash, session/reset state |
| supply_chain_nodes | Typed supplier, warehouse, manufacturer, distribution, retail nodes; location, capacity, risk |
| supply_chain_edges | source/target → nodes; directed transport routes |
| categories | Product classification |
| products | category_id → categories; supplier_id → nodes; SKU, cost, daily demand |
| inventory | product_id → products; warehouse_id → nodes; quantity, reserved, safety/reorder levels |
| inventory_transactions | inventory_id → inventory; quantity delta and reason |
| orders | warehouse_id → nodes; customer, quantity, value, dates, status/risk |
| order_items | order_id → orders; product_id → products |
| shipments | order_id → orders; origin/destination → nodes; carrier, location, delivery, delay |
| shipment_events | shipment_id → shipments; timestamped milestone |
| disruptions | node_id → nodes; probability, impact, risk, severity, root cause, financial impact |
| simulations | user_id → users; disruption_id → disruptions; JSON configuration and computed impact |
| recovery_plans | disruption_id → disruptions; strategy, cost, recovery time, approval state, impact references |
| recovery_actions | plan_id → recovery_plans; execution history |
| agent_executions | Named stage, status, decision mode, structured JSON output |
| notifications | Shared workspace notification, severity, read state, simulated flag |
| audit_logs | user_id → users; action, structured metadata, timestamp |

All tables use primary keys. Frequently queried emails, node types/regions, statuses, agent names, and key operational relationships are indexed. Schema is 19 tables; typed nodes and JSON impact/results avoid duplicating data in the original proposed 25-table layout.

## Simulation

The deterministic simulator starts from the selected node and traverses directed edges to a fixed point. It adds inventory supplied by affected suppliers and gathers active orders/shipments from exposed warehouses. Exposed demand is daily demand × duration × severity. Available stock is quantity − reserved. Shortage is max(0, exposed demand − available). Financial impact combines exposure cost and order value coefficients. Risk uses normalized severity, duration, and affected order count. Four heuristic strategies compare cost, recovery time, fulfillment, and operational risk. All scenario labels currently use this shared generic exposure engine.

## Agent architecture

LangGraph StateGraph runs Monitoring → Disruption Detection → Demand Forecasting → Risk Assessment → Digital Twin Simulation → Recovery Planning → Decision. Each stage records a structured execution. The decision uses a weighted comparison of cost, recovery hours, and fulfillment loss to propose a plan. The graph ends at a durable Pending approval plan. The HTTP approval endpoint supplies the human boundary. Execution and Reporting records are added only after a manager explicitly approves and executes the plan. This initial implementation uses common precomputed simulation context and stage-specific responsibilities, not independent LLM reasoning.

Execution locks the plan row where supported, requires Approved, updates affected simulated records in the same transaction, writes stock/shipment/action history, resolves the disruption, and adds completion notifications. Repeat execution is rejected. Synthetic seed example plans have no impacted-record list; generate a simulation to exercise operational updates.

## ML

`python -m app.ml.train historical.csv --task demand` evaluates Random Forest Regressor, Gradient Boosting, and a moving average baseline using a chronological 80/20 split, MAE, RMSE, and R². `--task risk` evaluates Random Forest Classifier and standardized Logistic Regression with precision, recall, F1, and ROC-AUC. At least 100 complete dated records are required; risk training additionally requires both classes in both partitions. No model is automatically deployed. The application truthfully uses rule-based scoring and seeded daily-demand estimates until a trained inference service is integrated.

## Browser sandbox

When `VITE_SANDBOX=true` is explicitly configured, an IndexedDB adapter provides synthetic demo operations. It does not simulate JWT security or claim to run Python. Account forms explain that sandbox mode has no cloud authentication. Records remain in the current origin/browser. Production does not enable this adapter.
