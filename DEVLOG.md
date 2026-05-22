# Devlog — Nimadhn/time node

Informal session notes. Newest entry at the top.

---

## 2026-05-22 — Upstream merge + node goes live

Merged all upstream commits into the fork. Key changes pulled in:

- **Handle format breaking change** — `::slot:slot:slot::` dropped in favour of
  `slot:slot:slot`. Ran `migrations/001_drop_handle_delimiters.py` against the
  live DB (2 users migrated cleanly).
- **DEPLOY.md** added upstream — full operator runbook for both systemd (Path A)
  and pm2/shared-hosting (Path B).
- **Ledger explorer** (`ledger.py`, `tools/generate_ledger_site.py`) — static
  public ledger site generator, not yet deployed here.
- **signing.py** — cryptographic signing primitives, groundwork for the
  cross-node federation transfers coming in `feat/federation-v1`.

Bot running as a systemd service (`ubi-bot.service`), polling as `@chronomastbot`.
Auto-restarts on failure, enabled on boot.

Next: notifying the main operator that this node is up and ready to test
cross-node transfers once `feat/federation-v1` ships.

---

## 2026-05-22 — Fork setup + initial ideas doc

Forked `github.com/UBIworld/time`, cloned locally, installed dependencies into
`.venv`, created `.env` with bot token and admin ID.

Added `IDEAS.md` — brainstormed admin/operator ecosystem (Datasette, Streamlit,
Metabase, Grafana, seed scripts, Jupyter sim, Locust, FastAPI layer, Docker
Compose, public web portal, network visualizer, node config UI). Each entry has
a "works well when / falls short when" section and a suggested build order.

Bot not yet running as a service at end of this session.
