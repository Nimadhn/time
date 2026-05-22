# Ledger MVP — Data Model & Signing

Short reference for the `feat/ledger-mvp` branch. Pedro's design brief at
`Stefano's Inbox/ubi-world-explorer-design-2026-05-22.md` covers the
visitor-facing surface; this file covers what's written on disk.

## On-disk layout

```
/home/vrgli/ubi.world/                      <- web root, ledger lives under it
├── index.html                              <- home dashboard (generated)
├── ledger/
│   ├── transactions/
│   │   ├── tx_00000001.json                <- one file per transaction (signed)
│   │   ├── tx_00000002.json
│   │   └── ...
│   ├── README.txt                          <- explainer for audit-curious humans
│   └── nodes/                              <- reserved for Stage 2b
├── tx/
│   ├── tx_00000001.html                    <- one file per transaction (generated)
│   └── ...
├── handle/
│   ├── house:cat:888.html                  <- one file per handle (generated)
│   └── ...
└── style.css                               <- shared design tokens
```

Generated HTML lives ABOVE the `ledger/` dir; the signed JSONs are the
ground truth and stay at `/ledger/transactions/`.

## Transaction JSON shape (v1.0)

```json
{
  "ledger_format_version": "1.0",
  "id": "tx_00000001",
  "type": "transfer",
  "from_handle": "trader:joe:888",
  "to_handle": "house:cat:888",
  "from_node": "cat.ubi.asia",
  "to_node": "cat.ubi.asia",
  "amount_seconds": 5710,
  "blue_pct": 100,
  "timestamp_iso": "2026-05-16T13:36:50Z",
  "node_signature": "<base64 Ed25519 over canonical form>",
  "signed_at_iso": "2026-05-22T17:34:25Z",
  "signing_node_domain": "cat.ubi.asia",
  "signing_node_public_key_fingerprint": "a1b2:c3d4:e5f6:7890"
}
```

For local transactions, `from_node == to_node`. The same shape is
reserved for the future `daily_settlement` and `universal_circle_flow`
types — the `type` field discriminates and the other fields can be
namespaced without a v1.0 bump.

## Signing — canonical form

1. Take the entry object.
2. Drop the `node_signature` field (always; it's the signature itself).
3. Serialise as JSON with `sort_keys=True`, `separators=(",", ":")`,
   `ensure_ascii=False`.
4. Encode UTF-8.
5. The signature is Ed25519 over those bytes, base64-encoded, stored
   back into `node_signature`.

Anyone with the node's public key (published at
`/.well-known/ubi-node`, Stage 2a) can verify offline:

```python
import json, base64, nacl.signing
entry = json.load(open("tx_00000001.json"))
sig = base64.b64decode(entry.pop("node_signature"))
msg = json.dumps(entry, sort_keys=True, separators=(",", ":"),
                 ensure_ascii=False).encode("utf-8")
nacl.signing.VerifyKey(base64.b64decode(NODE_PUBKEY_B64)).verify(msg, sig)
```

## Keys

`signing.py` reuses the same on-disk format as Stage 2a's
`federation.py` so the two can share the keypair once both land. Files
live at `~/.ubi-bot/node_private_key.pem` (mode 600) and
`node_public_key.pem` (mode 644). Created automatically on first ledger
write.

## Failure semantics

The ledger is a mirror of the SQLite DB, never the source of truth. If
the ledger write fails (disk full, perms wrong, sig key missing), the
bot logs ERROR and continues. The DB transaction has already
committed. The backfill script (`python3 ledger.py`) can be re-run any
time to fill gaps — it skips files that already exist.

## Real-time feel

A cron job runs `tools/generate_ledger_site.py` every 60 seconds. From
the user's perspective: send time in Telegram → bot writes the row to
`transactions` and signs a JSON to disk → next minute, cron regenerates
the three page types → the new transaction is visible at
`https://ubi.world/`. Worst-case latency: ~60 seconds plus Cloudflare
edge-cache TTL.
