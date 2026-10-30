# Handoff: News Comment Assistant

You are setting up a new project in this empty folder. Read this whole file before writing any code. Build **one phase at a time**, stop at the end of each phase, and summarize what you built, how to run it, and what's next. Don't start the next phase until I confirm.

---

## 1. What we're building

A web app that helps a small team respond to posts from a list of news accounts (TikTok, Facebook, and news sites).

1. A person adds **sources** (news accounts / feeds) once.
2. The app **automatically fetches new posts** from those sources.
3. An LLM **scores each post for relevance** against our rules and **drafts 2–3 candidate comments** using a configurable system prompt.
4. A human **reviews every draft** in a queue: edit, approve, reject, or regenerate.
5. Approved comments are **published** from our single official account per platform, and everything is logged.

Human approval is mandatory. Nothing gets published without an approved draft.

---

## 2. Tech stack

| Layer | Choice |
|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 16 |
| Queue / jobs | Redis + ARQ (async job queue that fits FastAPI) |
| LLM | Anthropic Python SDK; model name read from env `ANTHROPIC_MODEL` (default `claude-sonnet-5-5`) |
| Frontend | React + TypeScript + Vite, React Router, TanStack Query, Tailwind CSS |
| Realtime | FastAPI WebSocket for live review-queue updates |
| Auth | JWT (access token), bcrypt password hashing |
| Secrets | Fernet encryption (key from env) for any stored account credentials |
| Dev env | Docker Compose: `postgres`, `redis`, `backend`, `worker`, `frontend` |
| Tests | pytest + httpx for backend, Vitest for frontend |

---

## 3. Repository layout

```
.
├── docker-compose.yml
├── .env.example
├── README.md
├── HANDOFF.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, routers, CORS, /health
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings, reads env
│   │   │   ├── security.py         # JWT, password hashing
│   │   │   └── crypto.py           # Fernet encrypt/decrypt helpers
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   ├── models/                 # SQLAlchemy models (one file per table)
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── api/v1/
│   │   │   ├── router.py
│   │   │   └── routes/             # auth, sources, templates, posts, drafts, activity, ws
│   │   ├── services/               # business logic, no HTTP code here
│   │   ├── adapters/
│   │   │   ├── sources/            # how posts are FETCHED
│   │   │   │   ├── base.py         # SourceAdapter interface
│   │   │   │   ├── rss.py          # implemented
│   │   │   │   ├── manual.py       # "add a post by URL" - implemented
│   │   │   │   └── meta_graph.py   # stub for now
│   │   │   └── publishers/         # how comments are PUBLISHED
│   │   │       ├── base.py         # Publisher interface
│   │   │       ├── manual.py       # implemented (default)
│   │   │       └── automated.py    # stub only, behind feature flag
│   │   ├── llm/
│   │   │   ├── client.py           # thin wrapper around Anthropic SDK
│   │   │   └── prompts.py          # builds relevance + drafting prompts
│   │   └── workers/
│   │       ├── settings.py         # ARQ WorkerSettings + cron jobs
│   │       └── jobs.py             # poll_source, score_post, draft_comments, publish_draft
│   └── tests/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/                    # typed fetch client + TanStack Query hooks
        ├── components/
        └── pages/
            ├── Login.tsx
            ├── Sources.tsx
            ├── Templates.tsx
            ├── ReviewQueue.tsx
            ├── Activity.tsx
            └── Settings.tsx
```

---

## 4. Data model (PostgreSQL)

Use UUID primary keys and `created_at` / `updated_at` timestamps on every table.

- **users**: email (unique), password_hash, role (`admin` | `reviewer`), is_active
- **prompt_templates**: name, system_prompt (text), tone, language, max_length (int), relevance_rules (text: what to engage with and what to skip), version (int), is_active
- **sources**: platform (`tiktok` | `facebook` | `rss` | `manual`), display_name, url_or_handle, adapter (string key), prompt_template_id (FK), poll_interval_minutes (default 15), is_active, last_checked_at
- **posts**: source_id (FK), platform_post_id, url, text, thumbnail_url, published_at, fetched_at, relevance_score (float, nullable), relevance_reason (text), status (`new` | `skipped` | `drafted`). **Unique (source_id, platform_post_id)** for dedupe.
- **drafts**: post_id (FK), template_id (FK), template_version, text, edited_text (nullable), status (`pending` | `approved` | `rejected` | `published` | `failed`), model_name, reviewer_id (FK, nullable), reviewed_at, published_at, error (text, nullable)
- **posting_accounts**: platform (unique; **one account per platform**), display_name, encrypted_credentials (nullable; not needed in manual mode), is_active
- **audit_log**: actor_id (nullable for system), action, entity_type, entity_id, payload (JSONB), created_at

---

## 5. API (prefix `/api/v1`)

- `POST /auth/login`, `GET /auth/me`
- `GET/POST /sources`, `GET/PATCH/DELETE /sources/{id}`, `POST /sources/{id}/poll-now`
- `GET/POST /templates`, `GET/PATCH/DELETE /templates/{id}`, `POST /templates/{id}/preview` (run the template against sample post text and return drafts without saving)
- `GET /posts?status=&source_id=&min_score=`, `GET /posts/{id}`
- `GET /drafts?status=pending`
- `PATCH /drafts/{id}` (edit text)
- `POST /drafts/{id}/approve`, `POST /drafts/{id}/reject`, `POST /posts/{id}/regenerate`
- `POST /drafts/{id}/mark-published` (used by manual publishing)
- `GET /activity` (audit log, paginated)
- `WS /ws/queue` (pushes `draft.created`, `draft.updated`, `post.created` events)
- `GET /health`

---

## 6. Background jobs (ARQ)

1. **poll_source(source_id)**: run by a cron every minute for sources that are due. Calls the source adapter, inserts new posts (dedupe by unique key), and enqueues `score_post` for each.
2. **score_post(post_id)**: LLM call that returns JSON `{ "relevant": bool, "score": 0-1, "reason": str }` using the template's `relevance_rules`. Below the threshold (env `RELEVANCE_THRESHOLD`, default 0.6), set the post to `skipped`; otherwise enqueue `draft_comments`.
3. **draft_comments(post_id)**: LLM call that returns JSON `{ "drafts": [str, str, str] }` built from the template's system_prompt, tone, language, and max_length plus the post text. Saves drafts as `pending` and emits a WebSocket event.
4. **publish_draft(draft_id)**: **must refuse unless the draft status is `approved`.** Uses the configured publisher, records the result in `drafts` and `audit_log`, and enforces a per-platform rate limit (env `MAX_COMMENTS_PER_HOUR`, default 10).

LLM rules:
- Use structured JSON output and validate with Pydantic.
- Retry once on invalid JSON.
- Log the model name and template version on every draft.

---

## 7. Adapters

### Source adapters (fetching)
```python
class SourceAdapter(Protocol):
    key: str
    async def fetch_new_posts(self, source: Source, since: datetime | None) -> list[FetchedPost]: ...
```
- **rss**: implement now with `feedparser` or `httpx`. Works for news websites.
- **manual**: implement now. A user pastes a post URL plus text in the UI.
- **meta_graph**: stub that raises `NotImplementedError` with a docstring. It needs Meta's public Page content access, which requires app review.
- No TikTok fetcher yet. Leave a TODO; we'll decide between an official API and a licensed data provider later.

### Publishers (posting)
```python
class Publisher(Protocol):
    key: str
    async def publish(self, draft: Draft, post: Post, account: PostingAccount) -> PublishResult: ...
```
- **manual** (default): "publishing" means the UI shows a **Copy comment + Open post** button. The reviewer pastes and posts it themselves, then clicks **Mark as published**.
- **automated**: create the interface and file only, raising `NotImplementedError`. Gate it behind env `ENABLE_AUTOMATED_PUBLISHING=false`. Do not implement browser automation in this build.

---

## 8. Frontend pages

- **Login**
- **Sources**: table of sources with add/edit dialog (platform, URL/handle, template, interval, active toggle) and a "Poll now" button.
- **Templates**: edit system prompt, tone, language, max length, and relevance rules. A **Preview** panel tests the template against pasted sample text.
- **Review queue** (main screen): a feed of cards, newest first. Each card shows source, post preview and link, the relevance reason, and the drafts. Every draft has inline edit plus Approve / Reject buttons, and each post has Regenerate. Approved drafts in manual mode show Copy + Open post + Mark as published. The queue updates live over the WebSocket.
- **Activity**: filterable audit log.
- **Settings**: posting account per platform (display name only in manual mode), relevance threshold, rate limit.

---

## 9. Guardrails (non-negotiable; enforce in backend code, not just UI)

- Every published comment must come from a draft with status `approved` and a recorded reviewer.
- One posting account per platform. No multi-account rotation.
- No proxy rotation, browser fingerprint spoofing, CAPTCHA solving, or other bot-detection evasion.
- Rate limiting on publishing is enforced server-side.
- Default relevance rules skip posts about deaths, tragedies, and violence unless a template explicitly allows them.
- Drafted comments must not claim to be from an independent or unaffiliated person. They speak as our account.
- Credentials are encrypted at rest, never logged, and never returned by the API.

---

## 10. Environment (`.env.example`)

```
DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/app
REDIS_URL=redis://redis:6379/0
JWT_SECRET=change-me
FERNET_KEY=generate-with-cryptography-fernet
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5-5
RELEVANCE_THRESHOLD=0.6
MAX_COMMENTS_PER_HOUR=10
ENABLE_AUTOMATED_PUBLISHING=false
FRONTEND_ORIGIN=http://localhost:5173
```

---

## 11. Build phases

Stop after each phase and report back.

**Phase 1: Skeleton**
- docker-compose with all five services; backend `/health`; Alembic set up with all models from section 4; seed script that creates an admin user.
- JWT login; React app with routing, login page, and an empty protected layout.
- Done when: `docker compose up` runs cleanly, `/health` returns ok, and I can log in.

**Phase 2: Sources and templates**
- CRUD API + pages for sources and templates, and the template preview endpoint.
- Done when: I can create a template, preview drafts from sample text, and attach it to a source.

**Phase 3: Ingestion**
- SourceAdapter interface, RSS and manual adapters, ARQ worker with the cron poller, dedupe, and a posts list in the UI.
- Done when: adding an RSS feed shows new posts within one poll interval with no duplicates.

**Phase 4: Scoring and drafting**
- `score_post` and `draft_comments` jobs with validated JSON output.
- Done when: new posts are either skipped (with a reason) or get pending drafts.

**Phase 5: Review queue**
- Review queue page, WebSocket updates, edit / approve / reject / regenerate, and audit logging.
- Done when: a reviewer can process the queue end to end and every action appears in Activity.

**Phase 6: Publishing (manual)**
- Publisher interface, manual publisher flow in the UI, mark-as-published, server-side approval check and rate limit, and the automated publisher stub behind the flag.
- Done when: an approved draft can be copied, opened, and marked published, and publishing a non-approved draft is rejected by the API.

**Phase 7: Hardening**
- Tests for services and guardrails, error handling, pagination, README with setup steps.

---

## 12. Conventions

- Type hints everywhere; `ruff` + `black` for Python; ESLint + Prettier for TypeScript.
- Business logic lives in `services/`. Routes stay thin.
- Every state change to a draft writes an `audit_log` row.
- Keep secrets out of git; commit only `.env.example`.
- Ask me before adding any dependency not listed here.
