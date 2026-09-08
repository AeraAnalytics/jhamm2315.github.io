# Aera Operations — implementation v0.1

A local, single-owner backend for opportunity research and paperwork operations. Research
may discover development, service, product, government, and fulfillment opportunities;
every model-produced result remains an **unverified candidate**. Aera does not purchase,
file, sign, contact, or certify anything.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
uv run aera init
uv run aera demo
uv run pytest -q
uv run aera doctor
```

Production data defaults to `runtime/aera.db`; the repeatable, synthetic demo uses
`runtime/demo.db`. Runtime files, secrets, and private keys are ignored by Git.

## Owner API

Set a random `AERA_OWNER_TOKEN` containing at least 32 characters, then run:

```bash
uv run aera serve --port 8421
```

The server binds to `127.0.0.1`. `/health` is public; every other endpoint (including the
private schema at `/schema`) requires `Authorization: Bearer <token>`. Do not put the token
in a URL. This is a local single-operator application—not a public service.

## Safety model

- All money is integer US cents. Research requires an exact-payload approval, an unexpired
  approval, a transactional budget reservation, and one-time queueing.
- A reservation is an internal control, **not** a provider invoice ceiling. Failed calls
  retain their reservations pending reconciliation; overruns pause spending.
- Owner selection does not verify evidence. Paperwork contains only verified public business
  fields and creates blockers for identity, tax, banking, and signature data.
- Vault documents are Fernet-encrypted and only addressable by opaque IDs. The research
  adapter and HTTP API have no vault access.
- Daily scheduling deduplicates on the America/Denver calendar date. Expired running leases
  are quarantined as `needs_review`, never silently replayed.

## Live research

Live research is off by default. The adapter is optional and refuses to run unless
`AERA_LIVE_RESEARCH=true` and `OPENAI_API_KEY` are present. Configure `AERA_MODEL` and
provider-side billing controls before enabling it. Model candidates cannot set verified or
selected status. The existing ChatGPT task scheduler is separate from this worker.

```bash
uv run aera worker --loop
```

See [`docs/api_examples.json`](docs/api_examples.json) for nonsensitive request shapes and
[`src/aera/models.py`](src/aera/models.py) for schemas. Never submit personal identifiers in
generic research queries or outcome observations.

## Known limits

No API key, deployment, transport, bank/wallet, sales worker, fulfillment worker, official
form adapter, or legal filing integration is included. Inbox records are local notifications.
SQLite itself is not encrypted and is intended for a single host. The application audit log
is append-only through application methods but cannot resist a machine administrator.
