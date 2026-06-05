# Contributing

## Development Setup

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Install frontend dependencies:

```bash
npm --prefix frontend install
npm --prefix frontend/api install
```

3. Create local config files:

```bash
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
```

These files are local-only and must not be committed.

## Verification

Run the main checks before opening a PR:

```bash
python3 -m pytest tests
npm --prefix frontend run build
npm --prefix frontend/api run build
```

## Pull Request Rules

- Keep changes scoped to a single concern when possible.
- Do not commit secrets, local `.env` files, runtime data, or generated evidence.
- Update docs when changing public behavior, config, or deployment flow.
- Prefer adding or updating tests when fixing behavior.

## Repository Hygiene

The following are intentionally excluded from version control:

- local env/config files such as `.env`, `.env.intranet`, `config/settings.yaml`
- runtime data under `data/`
- local planning/evidence under `.sisyphus/`
- generated build artifacts
