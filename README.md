# Memory Graph

Memory Graph is a self-hosted personal memory system for AI conversations, notes, files, and IDE activity. It imports local knowledge sources into a graph-backed memory store and uses GraphRAG-style retrieval to help you find previous decisions, context, and facts.

The project is designed for a single-user local deployment. It includes a React web app, a FastAPI backend, an optional NestJS sidecar, and an MCP server for agent integrations.

## What It Does

- Imports conversations and local files from supported AI IDE and chat sources.
- Normalizes imported content into memories, entities, relationships, and communities.
- Provides local, global, and hybrid GraphRAG retrieval flows.
- Exposes a web UI for dashboard, search, graph exploration, memories, communities, imports, diagnostics, and settings.
- Provides HTTP APIs for integration and automation.
- Provides an MCP server for tools such as Claude Desktop, Cursor, and OpenAI Agents.
- Keeps local runtime data, credentials, and generated evidence outside version control.

## Status

Memory Graph is usable for local single-user self-hosting. The current repository focuses on the Web + API + MCP stack, not on hosted multi-user service operations.

Known boundaries:

- You must provide your own LLM and embedding provider configuration.
- Local runtime data is stored under `data/` and is not committed.
- Some real-stack QA scripts require local services, browser dependencies, and provider credentials.

## Tech Stack

- Frontend: React, Vite, D3
- Backend: FastAPI, Pydantic, Python
- Sidecar: NestJS
- Retrieval/storage: GraphRAG-oriented core modules, FAISS vector persistence
- Agent integration: FastMCP
- Tests: pytest, Node test runner, Playwright-oriented smoke scripts

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- npm
- At least one supported LLM provider key, or a local provider configured in `config/settings.yaml`

## Quick Start

Create local configuration files:

```bash
pip install -r requirements.txt
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
```

Edit `.env` and `config/settings.yaml` before starting the API. At minimum, set:

```bash
MEMORY_GRAPH_API_TOKEN=replace-with-a-local-token
OPENAI_API_KEY=replace-if-using-openai
```

Start the backend:

```bash
PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the web app:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Optional Services

Build and run the NestJS sidecar:

```bash
npm --prefix frontend/api install
npm --prefix frontend/api run build
HOST=127.0.0.1 PORT=3001 npm --prefix frontend/api run start
```

Run the MCP server over stdio:

```bash
python3 -m src.mcp --transport stdio
```

See [docs/MCP_CLIENTS.md](docs/MCP_CLIENTS.md) for client configuration examples.

## Production Build

```bash
npm --prefix frontend install
npm --prefix frontend run build
npm --prefix frontend/api install
npm --prefix frontend/api run build

SIDECAR_BASE_URL=http://127.0.0.1:3001 \
PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

After building the frontend, the backend can serve the web app from `frontend/dist`.

## Project Layout

```text
Memory_graph/
├── src/
│   ├── api/          # FastAPI app, schemas, routes, auth, diagnostics
│   ├── core/         # collectors, graph store, vector store, retrieval, sync, memory layers
│   └── mcp/          # FastMCP server and MCP service layer
├── frontend/
│   ├── src-react/    # React web app and browser QA scripts
│   └── api/          # optional NestJS sidecar
├── config/           # checked-in example config only
├── docs/             # architecture, API, deployment, MCP, roadmap
├── scripts/          # docs, QA, deployment, and sync helpers
└── tests/            # pytest suite
```

## Configuration

Local-only files:

- `.env`
- `config/settings.yaml`
- `data/`
- `.sisyphus/`
- generated browser, build, and test artifacts

Tracked examples:

- [.env.example](.env.example)
- [config/settings.example.yaml](config/settings.example.yaml)
- [scripts/deployment/.env.intranet.example](scripts/deployment/.env.intranet.example)

Do not commit real API keys, passwords, database files, local evidence, or imported memory data.

## Verification

Run the Python test suite:

```bash
python3 -m pytest tests
```

Run core documentation and frontend checks:

```bash
python3 scripts/generate_api_docs.py --check
npm --prefix frontend run build
npm --prefix frontend/api run build
```

Run the real-stack smoke test when local browser and service dependencies are available:

```bash
npm --prefix frontend run qa:real-stack-smoke
```

## Documentation

| Document | Purpose |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, modules, data model, retrieval flow, and design notes |
| [docs/API.md](docs/API.md) | Generated HTTP API reference |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Development setup, configuration, QA commands, and maintenance workflow |
| [docs/DELIVERY.md](docs/DELIVERY.md) | Local delivery scope and deployment notes |
| [docs/MCP_CLIENTS.md](docs/MCP_CLIENTS.md) | MCP client setup examples |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Planned phases, milestones, and known risks |
| [docs/FINAL_ACCEPTANCE.md](docs/FINAL_ACCEPTANCE.md) | Current acceptance scope and remaining boundaries |

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting guidance.

This project is intended for local self-hosting. Keep API auth enabled, use a strong `MEMORY_GRAPH_API_TOKEN`, and do not expose the service publicly without a reverse proxy, TLS, and an explicit access-control layer.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, verification, pull request, and repository hygiene rules.

## License

Apache License 2.0. See [LICENSE](LICENSE).
