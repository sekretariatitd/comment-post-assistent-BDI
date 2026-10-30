# News Comment Assistant

A web app that collects posts from chosen Facebook pages, TikTok accounts and RSS feeds. It scores each post with Claude and drafts 2–3 comments using editable templates. A person reviews every draft before posting it manually. The full spec and the build phases are in [HANDOFF.md](HANDOFF.md).

## Start the app

Requires Docker Desktop. Start it first.

```sh
docker compose up -d --build   # start everything in the background (first run or after dependency changes)
docker compose up -d           # start again later
docker compose ps              # check that all 5 services are running
docker compose logs -f         # follow logs (Ctrl+C stops following, not the app)
docker compose down            # stop (data is kept)
docker compose down -v         # stop AND delete the database
```

| URL | What |
|---|---|
| http://localhost:5173 | Web app. Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env` |
| http://localhost:8000/health | Health check (database and Redis) |
| http://localhost:8000/docs | API docs |

`.env` is required and is gitignored; copy it from `.env.example`. Generate a `FERNET_KEY` with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Template preview and drafting also need `ANTHROPIC_API_KEY`.

On startup the backend runs `alembic upgrade head`, seeds the admin user if it's missing, then serves the API.

## Services

`postgres`, `redis`, `backend` (FastAPI, auto-reloads), `worker` (ARQ: polling, scoring, drafting), and `frontend` (Vite, auto-reloads). Backend and worker share one image, `news-comment-assistant-backend`.

- **The worker does not auto-reload.** After changing backend code, run `docker compose restart worker`.
- After changing `backend/pyproject.toml`, run `docker compose up -d --build backend worker`.
- After changing `.env`, run `docker compose up -d --force-recreate backend worker`.

## Checks

```sh
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec backend black --check .
docker compose exec frontend npm run lint
docker compose exec frontend npm test -- --run
docker compose exec frontend npm run build
```

Backend tests run against a throwaway `app_test` database built with the real migrations. They use a fake LLM and a fake queue, so they never call Anthropic or the real worker.

New migration: `docker compose exec backend alembic revision --autogenerate -m "describe change"`, then review the file it generates.

## How it fits together

- **Prompts:** templates (who we are, stance, facts, tone, language, relevance rules, plus the ë/ç→e/c and no-dash switches) live in the **database** and are edited on the Templates page. `backend/app/llm/prompts.py` holds the fixed parts that apply to every template: the hard rules, the drafting method, the sensitive-topics baseline, and how a prompt is assembled.
- **Sources** each have a stance (`ally`, `opponent` or `neutral`) that is sent with every post, so drafts back allies and criticise opponents whichever template is used.
- **Ingestion:** RSS is polled automatically. Facebook and TikTok posts get in via **Posts → Import**, by pasting a GraphQL or `item_list` Response copied from the user's own browser, or via **Add post**. The server never calls Facebook or TikTok internal endpoints. Getting past their bot checks is off-limits, and the Meta Graph adapter is a stub until Meta App Review.
- **Flow:** a new post triggers `score_post`, then `draft_comments` if it is relevant (or a person clicks "Draft comments"). A reviewer edits, approves or rejects drafts in the Review queue, posts an approved comment by hand, then clicks "Mark as published". `review_service.publish` refuses anything that is not approved with a recorded reviewer, needs an active posting account for the platform (Settings), and enforces `MAX_COMMENTS_PER_HOUR`.
- **Live updates:** the API and worker publish `post.created` / `draft.created` / `draft.updated` to the Redis channel `queue-events`; `WS /api/v1/ws/queue?token=` forwards them to browsers.

## Conventions

- Build one HANDOFF.md phase at a time and stop for confirmation. Phases 1–6 are done; Phase 7 (hardening: tests, error handling, pagination, README) is next.
- Ask before adding any dependency not listed in HANDOFF.md.
- Business logic goes in `backend/app/services/`; routes stay thin. Every draft state change writes an `audit_log` row.
- Python: type hints, `ruff` + `black` (line length 100). TypeScript: ESLint + Prettier.
- Never commit `.env` or put credentials in code, logs or API responses.
