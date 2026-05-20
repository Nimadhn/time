# UBI World — Admin & Operator Ecosystem

Reference document for tooling, analytics, and infrastructure ideas around the
time-based UBI protocol. Each entry includes a short description, where it shines,
and where it falls short.

---

## 1. Observability

### Datasette
Point it at `ubi_bot.db` and you instantly get a browsable, filterable,
SQL-queryable web UI with zero code. Supports publishing read-only to the web.
Handles the `users`, `transactions`, `daily_resets`, `universal_circles_pool`,
and `community_circles` tables out of the box.

**Works well when:**
- You need immediate visibility during development or early testing
- Non-technical stakeholders (NGO directors, researchers) need to browse data
  without writing SQL
- You want to publish a read-only public view of node statistics
- Debugging a specific account or transaction after a bug report

**Falls short when:**
- You need real-time updates (Datasette is request-based, not push)
- You want charts or trend visualizations rather than raw table data
- Your DB moves to Postgres (Datasette is SQLite-native; Postgres support is a
  plugin and less polished)
- You need write access or admin actions — it is strictly read-only

---

### Uptime Kuma
Self-hosted Docker container that monitors the bot and the daily settlement job
(23:59:59 UTC is the most critical moment). Sends alerts via Telegram, which
means the bot effectively monitors itself. Tracks HTTP endpoints, TCP ports,
and cron-style heartbeats.

**Works well when:**
- You need to know immediately when the settlement job misses its window
- Running on a VPS or single server where you want simple uptime history
- The operator lives in Telegram — alerts land in the same app they already use
- You want a status page to share with node members showing historical uptime

**Falls short when:**
- You need distributed or multi-region monitoring (Uptime Kuma is single-node)
- The bot crashes silently without an HTTP endpoint to probe — you need to
  instrument a heartbeat endpoint yourself for it to detect Python process failures
- You want anomaly detection beyond up/down (e.g., settlement ran but processed
  0 users — that's a logic failure, not a connectivity failure)

---

## 2. Analytics

### Streamlit Dashboard
~200 lines of Python reading `ubi_bot.db` directly, showing: DAU/MAU, total
time in circulation, daily settlement history, vault tier distribution, circle
balances, top senders/receivers, Blue/Red time trends. Pure Python, fits the
existing stack, deployable in an afternoon.

**Works well when:**
- The team is already Python-fluent and wants full control over what's shown
- You need a quick internal dashboard before investing in heavier BI tooling
- Prototyping new metrics — adding a new chart is 5 lines of code
- Demoing the protocol to potential node operators or funders; live data is
  more persuasive than screenshots

**Falls short when:**
- Non-technical operators need to build their own queries or customize views —
  Streamlit requires Python to modify
- You have many concurrent users; Streamlit reruns the entire script per session
  and does not scale well under load
- You want scheduled reports or email digests — Streamlit is a live app, not a
  reporting pipeline
- The dashboard needs to stay up 24/7 without babysitting; it is a dev tool at
  heart, not a production service

---

### Metabase (self-hosted)
Non-technical BI. Node operators who are not developers can build their own
queries with a point-and-click interface, create dashboards, and schedule email
reports. Self-hosted via Docker, connects to SQLite or Postgres.

**Works well when:**
- Universities, NGOs, or community groups run their own node and need reporting
  without engineering support
- You want to share dashboards with community governance participants who need
  visibility into circle balances and flow patterns
- Scheduled weekly reports (e.g., how much went to each Universal Circle this
  week) need to land in someone's inbox automatically
- You want a proper permission model: some users see everything, members see
  only their own node's data

**Falls short when:**
- SQLite support in Metabase is limited — it works, but Postgres is the
  first-class citizen; plan the DB migration before committing to Metabase
- The Docker image is heavy (~1 GB) and sluggish on low-spec VPS instances that
  many early node operators will use
- Real-time queries: Metabase caches aggressively and is not the right tool for
  watching live transaction flow
- Small single-operator nodes will find it over-engineered; Datasette or
  Streamlit will serve them better

---

### Grafana
Time-series dashboards: transaction volume per hour, settlement totals per day,
circle accumulation curves, vault tier migration rates. Connect via a SQLite
plugin (development) or Postgres datasource (production). Produces the kind of
charts that appear in grant reports and investor decks.

**Works well when:**
- You want beautiful, live time-series charts that auto-refresh
- Multiple node operators federate and you want a single pane of glass across
  all of them (Grafana supports multiple datasources in one dashboard)
- You are already running Prometheus for infrastructure metrics and want to
  co-locate app metrics alongside server CPU/memory
- The settlement cadence (once per day) needs trend tracking over weeks and
  months — Grafana's time-range selector is ideal for this

**Falls short when:**
- The team wants non-technical users to build their own views — Grafana's query
  editor assumes familiarity with SQL or PromQL
- SQLite is the DB: the SQLite Grafana plugin is community-maintained and lags
  behind official datasources; flaky on some Grafana versions
- You need more than charts: Grafana does not do user lookup, account inspection,
  or any write operations
- Early stage with few users — dashboards look empty and misleading at <100 users;
  wait until there is real data worth trending

---

## 3. Testing & Simulation

### Seed Script (`seed.py`)
Generates N fake users with realistic transaction distributions, runs N days of
simulated resets, and prints steady-state economics: how much flows to Universal
Circles per day, vault tier distribution at equilibrium, average Blue/Red ratio.
Uses the existing `database.py` functions directly — no mocking.

**Works well when:**
- You need to answer "what does the economy look like at 1,000 users?" before
  you have 1,000 users
- Catching settlement edge cases (user with exactly 0 wallet at reset, vault
  exactly at capacity when a transfer arrives) before real users hit them
- Onboarding new node operators: run the seeder, show them live data in
  Datasette, let them feel the protocol before going live
- Regression testing: seed → run a code change → compare output against a
  known-good baseline

**Falls short when:**
- Simulated transaction patterns never fully match real human behavior — the
  seeder will miss usage patterns you did not think to model (e.g., users who
  never send, circles that go dormant)
- If the seeder uses the same DB as development, test data contaminates real
  data; needs a separate `ubi_bot_test.db` path in config
- Does not test the Telegram bot layer itself — only the database operations;
  a user registering via a bot command can still break even if the DB logic passes

---

### Jupyter Notebook (Economic Simulator)
Economic parameter explorer. Change `DAILY_WALLET_AMOUNT`, vault ceiling,
overflow thresholds, and circle distribution percentages, then see projected
outcomes as charts. Useful for researchers and for new node operators deciding
on their parameters before going live.

**Works well when:**
- Researchers, economists, or funders want to model the protocol's behavior
  under different configurations without touching code
- A node operator wants to run with different parameters from the reference
  implementation (e.g., 12-hour daily wallet instead of 24) and see the
  projected steady-state before committing
- Presenting the protocol to academic audiences — notebooks are a legible,
  reproducible research artifact
- Exploring questions like: does the 99-hour vault ceiling create enough
  circulation pressure, or does it stifle accumulation too aggressively?

**Falls short when:**
- The simulation is only as good as the behavioral model baked in — garbage in,
  garbage out; if the assumed send rate is wrong, the projections are wrong
- Notebooks are not a substitute for running the actual code with real users;
  emergent social behavior (circles forming, reciprocal gifting) cannot be
  modeled accurately in advance
- Maintenance burden: as the protocol evolves, the notebook must be kept in sync
  manually; it will drift unless someone owns it

---

### Locust (Load Testing)
Load tests the daily settlement job (`perform_daily_reset()`) with thousands of
simulated users. Identifies the scale at which the current sequential loop in
`database.py` becomes a bottleneck — important before the 23:59:59 deadline
becomes a missed deadline.

**Works well when:**
- You want a concrete number: "settlement takes X seconds at Y users" — sets
  a hard scaling ceiling before you hit it in production
- Benchmarking DB schema changes (adding indexes, switching to Postgres) to
  confirm the improvement is real
- CI pipeline gate: run a lightweight Locust scenario on every PR that touches
  `database.py` to catch regressions

**Falls short when:**
- Locust tests HTTP endpoints by default; the settlement job is a Python
  coroutine, not an HTTP call — requires a custom wrapper to expose it as a
  testable surface
- Load testing SQLite concurrency is partially artificial: SQLite serializes
  writes, so the bottleneck will always be the write lock, and the only real
  fix is Postgres — Locust just confirms what you already suspect
- Does not test correctness under load, only throughput; a race condition that
  corrupts balances will not be caught by Locust

---

## 4. Management

### Extended Admin Bot Commands
The current admin surface is just `/reboot`. Useful additions: user lookup by
handle or Telegram ID, manual vault/wallet inspect, on-demand settlement
trigger, circle health report, and a `frozen` flag on the `users` table for
bad actors. All within Telegram — the operator already lives there.

**Works well when:**
- The operator is mobile or remote and needs to act fast (investigate a report,
  freeze an account) without SSH access to a server
- The interface is Telegram anyway — keeping admin tools in the same app
  reduces context switching and lowers the bar for non-technical operators
- Node operators in communities where desktop access is inconsistent rely on
  mobile-first tools; a Telegram admin surface works anywhere

**Falls short when:**
- Complex operations (bulk user export, schema migration, parameter changes)
  are awkward in a chat interface; some things need a proper web UI
- Security surface: the `ADMIN_TELEGRAM_ID` check is a single gate; if an
  admin account is compromised, all admin commands are exposed with no 2FA
  or audit log
- Discoverability: new operators inheriting a node won't know what admin
  commands exist without documentation; a web panel with labeled buttons is
  more self-explanatory

---

### FastAPI REST Layer
Thin async API wrapper around the functions already in `database.py`. Unlocks:
a user-facing web portal, inter-node federation, webhook integrations, and
external tooling that queries the node programmatically. The `async def`
functions in `database.py` map directly to FastAPI endpoints with almost no
rewrite.

**Works well when:**
- You want a web portal, mobile app, or LINE/USSD interface that is not
  Telegram — all of them need an API to talk to
- Multiple nodes need to federate: cross-node transfers require a common HTTP
  interface between nodes
- Third-party developers (researchers, circle operators, community apps) want
  to build on top of a node without forking the bot code
- Audit and compliance: an API layer is easier to put behind authentication,
  rate limiting, and logging middleware than direct DB access

**Falls short when:**
- It is another service to deploy, monitor, and keep in sync with `database.py`;
  every schema change must be reflected in the API — adds maintenance overhead
- Premature for a single-node MVP with one Telegram interface; the complexity
  cost is not justified until you have a second consumer of the data
- Security must be designed carefully: public endpoints exposing wallet balances
  or transfer history need auth, rate limiting, and input validation that the
  current DB layer does not have

---

## 5. User-Facing

### Public Web Portal
Users enter their handle to see balance, transfer history, circle memberships,
and Blue/Red reputation score. Also a public "network stats" page: total
registered users, total time in circulation, Universal Circle balances. Built
on top of the FastAPI layer.

**Works well when:**
- Users want a visual summary of their account without navigating bot commands
- Transparency and auditability matter to the community — a public stats page
  shows the protocol is working as described
- Onboarding new users: a web page explaining the protocol with live stats is
  more persuasive than a Telegram conversation
- Potential node operators evaluate whether to join — they want to see real
  activity, not just a README

**Falls short when:**
- Requires the FastAPI layer to exist first — not a standalone project
- Handle-based lookups are pseudonymous but not anonymous; a sufficiently
  motivated observer could correlate handles to identities via transfer graphs;
  the portal must not expose more than the protocol intends
- Mobile UX on Telegram is better than most self-built mobile web experiences;
  users who live in the bot may not bother with a separate web app

---

### Transfer Network Visualizer
D3.js force-directed graph showing who sends to whom (handles only, no
identity). Shows whether the economic graph is healthy (distributed) or
degenerate (hub-and-spoke, isolated clusters). Useful for researchers,
governance participants, and for demonstrating the protocol's behavior publicly.

**Works well when:**
- Presenting the protocol to researchers, funders, or policy audiences — a
  live network graph is immediately compelling in a way that tables are not
- Governance: community members can visually identify whether certain circles
  are capturing disproportionate flow and prompt a discussion
- Detecting degenerate patterns early: a hub-and-spoke graph with one user
  receiving most transfers is a sign of social dynamics worth examining

**Falls short when:**
- The graph becomes unreadable past a few hundred nodes — needs clustering,
  filtering, and time-windowing to remain useful at scale
- Privacy-sensitive: even pseudonymous handle graphs can be deanonymizing if
  the community is small and members know each other's handles
- High development cost for a visual that is primarily illustrative; deprioritize
  until there is enough real transaction data to make it meaningful

---

## 6. Scaling & Multi-Node

### Docker Compose Stack
`docker-compose.yml` bundling the bot + an analytics tool (Metabase or Grafana)
+ optional Postgres. One command to spin up a complete node. The single biggest
lever for making it easy for universities, NGOs, or community groups to run
their own node without a DevOps background.

**Works well when:**
- Lowering the barrier for independent node operators is a priority — and it
  should be, given that the protocol's value is in federation and diversity of nodes
- Reproducibility: every node starts from the same baseline configuration,
  reducing "works on my machine" support burden
- Testing: spin up a fresh node in CI, run the seed script, tear it down —
  clean, isolated, repeatable

**Falls short when:**
- Operators on shared hosting (cPanel, cheap shared Linux) cannot run Docker;
  a plain Python virtualenv install path must remain viable alongside the
  Compose path
- Docker Compose does not handle updates, migrations, or secrets rotation —
  operators still need to understand what they are running when something breaks
- A misconfigured Compose file is a silent failure mode; if the settlement
  container exits quietly, there is no time in the pool that night

---

### SQLite → PostgreSQL Migration
SQLite is appropriate to roughly 50,000 users under the current write pattern.
Beyond that, the WAL mode write lock on settlement day becomes a latency
problem. The `aiosqlite` calls in `database.py` map almost directly to
`asyncpg` — the migration is largely mechanical, but the time to plan for it
is before the schema grows more complex, not after.

**Works well when:**
- The node grows beyond the SQLite comfort zone and settlement timing becomes
  a concern
- Multiple services (bot + FastAPI layer + Metabase) need concurrent read/write
  access — Postgres handles this cleanly; SQLite's WAL mode is a workaround
- You want proper DB-level constraints, triggers, and `pg_cron` for scheduled
  jobs instead of APScheduler inside the Python process

**Falls short when:**
- Premature migration adds ops complexity for nodes that may never exceed
  10,000 users; SQLite with WAL is genuinely capable and requires zero infra
- Postgres requires a running server process, backups, and connection pooling —
  all of which SQLite sidesteps entirely; do not migrate until there is a
  concrete bottleneck, not a theoretical one
- Self-hosted nodes run by non-technical operators are harder to maintain with
  Postgres; the migration path must remain optional, not required

---

### Node Admin Config UI
Right now all parameters live hardcoded in `config.py`. A YAML config file
plus a small web form where a node operator sets `DAILY_WALLET_AMOUNT`, reset
timezone, settlement schedule, and circle distribution percentages makes it
possible for independent nodes to differentiate and experiment without touching
Python.

**Works well when:**
- Different communities want different economic parameters — a research node
  might want a 12-hour wallet to study circulation speed; a mutual aid group
  might want a higher vault ceiling
- Non-technical operators need to reconfigure without editing source files,
  which risks breaking syntax and is a support nightmare
- The protocol is in active research: parameterized nodes generate comparative
  data about which configurations produce healthier economies

**Falls short when:**
- Too much parameter freedom fragments the protocol; if every node has different
  rules, federation and cross-node transfers become undefined — some parameters
  should be locked to spec and not configurable
- A config UI is a new attack surface; a misconfigured node can silently violate
  protocol invariants (e.g., setting vault capacity above 99 hours breaks the
  Plato Ratio) — validation must be strict
- Adds scope to a project that is still proving the core mechanic; defer until
  the reference implementation is stable

---

## Suggested Build Order

| Priority | Tool | Reason |
|----------|------|---------|
| 1 | Datasette | Zero code, immediate DB visibility |
| 2 | Seed script + Jupyter sim | Understand the economics before real users |
| 3 | Streamlit dashboard | Admin visibility, pure Python |
| 4 | Extended admin bot commands | Operator actions without leaving Telegram |
| 5 | Uptime Kuma | Settlement monitoring before going public |
| 6 | FastAPI layer | Unlocks web portal and future federation |
| 7 | Docker Compose | Makes nodes reproducible for others |
| 8 | Metabase / Grafana | Once there is real data worth analyzing |
| 9 | Public web portal | After FastAPI layer is stable |
| 10 | SQLite → Postgres | When settlement timing becomes a measurable problem |
| 11 | Node config UI | After the reference implementation is stable |
| 12 | Transfer network visualizer | After meaningful transaction volume exists |
