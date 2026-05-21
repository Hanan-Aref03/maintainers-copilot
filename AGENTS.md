<!-- GSD:project-start source:.planning/PROJECT.md -->
## Project

Maintainers' Copilot is a FastAPI-based assistant for open-source maintainers. It classifies issues, extracts and retrieves repository knowledge, keeps short- and long-term memory, and exposes an embeddable widget plus supporting eval and data-prep tooling.

The project is organized as a backend API, a small model-server service, a React/Vite widget, and offline scripts for corpus building and evaluation.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:.planning/codebase/STACK.md -->
## Technology Stack

Python 3.11 backend, FastAPI, SQLAlchemy, Alembic, Postgres/pgvector, Redis, Vault, Gemini/Voyage integrations, and a React 19 + Vite widget. Python is managed with `uv`; the widget uses `npm`.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:.planning/codebase/CONVENTIONS.md -->
## Conventions

Python uses `snake_case`, React uses simple functional components and single quotes, and the backend follows a route/service/repository layering style. Logging is minimal today, so future code should be explicit about errors and boundaries.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:.planning/codebase/ARCHITECTURE.md -->
## Architecture

Layered FastAPI backend plus adjacent tooling: `app/` handles HTTP, services, repositories, and infra; `model_server/`, `widget/`, `data_pipeline/`, `evals/`, and `scripts/` support the product and CI flows.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found yet. Add skills under `.codex/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` when the project develops reusable workflows.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `$gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `$gsd-debug` for investigation and bug fixing
- `$gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `$gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` and is intentionally left as a placeholder.
<!-- GSD:profile-end -->
