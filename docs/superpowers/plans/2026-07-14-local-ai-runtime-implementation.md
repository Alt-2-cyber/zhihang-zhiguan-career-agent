# Local AI Runtime and Failover Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-orchestrated employment Agent with Zhipu-to-DeepSeek-to-local failover, PostgreSQL pgvector retrieval, forced PDF OCR, local BGE-M3, FunASR, and MeloTTS services, and a complete recorded voice interview flow.

**Architecture:** Keep the Python 3.13 FastAPI business service as the only public API. Add a PostgreSQL-backed durable AI task queue and worker, plus isolated CPU embedding/OCR services and a GPU speech service. Online LLM calls remain synchronous behind the existing `AgentGateway`; local document and speech work is asynchronous and visible through task status APIs.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL 17 + pgvector, httpx, Pydantic, React 19, TanStack Query, Docker Compose, FlagEmbedding BGE-M3, PaddleOCR PP-OCRv5, FunASR Paraformer, MeloTTS, FFmpeg, Playwright, pytest, Vitest.

---

## File Map

New backend modules:

- `backend/app/agents/openai_compatible.py`: structured OpenAI-compatible provider client.
- `backend/app/agents/failover.py`: retries, circuit breaker, provider ordering, and local fallback.
- `backend/app/agents/prompts.py`: operation-specific system prompts.
- `backend/app/agents/redaction.py`: deterministic PII redaction before external calls.
- `backend/app/ai/models.py`: durable task, document chunk, and media artifact models.
- `backend/app/ai/service.py`: enqueue, claim, heartbeat, retry, serialize, and artifact authorization.
- `backend/app/ai/router.py`: task, capability, and media APIs.
- `backend/app/ai/clients.py`: internal HTTP clients for embedding, OCR, and speech services.
- `backend/app/ai/worker.py`: task polling loop and handlers.
- `backend/app/jobs/retrieval.py`: chunking, vector persistence, and cosine retrieval.
- `backend/alembic/versions/9f12c3a4b5d6_local_ai_runtime.py`: pgvector and AI runtime schema.

New local services:

- `services/embedding/app.py`, `requirements.txt`, `Dockerfile`.
- `services/ocr/app.py`, `requirements.txt`, `Dockerfile`.
- `services/speech/app.py`, `requirements.txt`, `Dockerfile`.

Frontend changes:

- `frontend/src/app/api.ts`: authenticated blob downloads.
- `frontend/src/features/student/ResumePage.tsx`: asynchronous OCR status and retry.
- `frontend/src/features/student/InterviewPage.tsx`: recording, transcription review, and TTS playback.
- Focused component and Playwright tests for both flows.

Deployment changes:

- `docker-compose.yml`, `.env.example`, `.dockerignore`, `start-docker.bat`, `scripts/verify.ps1`, `README.md`.

## Task 1: Runtime Configuration and Secret-Safe Provider Selection

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing configuration tests**

Add tests that construct `Settings(_env_file=None)` with provider URLs, model IDs, service URLs, device choices, task timing, and retention values. Assert keys are accepted but excluded from any capability serialization helper.

```python
def test_failover_runtime_configuration(monkeypatch):
    monkeypatch.setenv("AGENT_PROVIDER", "failover")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")
    settings = Settings(_env_file=None)
    assert settings.zhipu_model == "glm-4-flash"
    assert settings.deepseek_model == "deepseek-v4-flash"
    assert settings.embedding_service_url == "http://embedding:8101"
    assert settings.audio_retention_days == 7
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_config.py -q`

Expected: failure because the new settings fields do not exist.

- [ ] **Step 3: Add typed settings and documented placeholders**

Add URL, model, timeout, circuit breaker, service URL, device, task lease, polling, and retention fields. Keep real keys out of `.env.example` and source control.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all configuration tests pass.

- [ ] **Step 5: Configure local ignored `.env`**

Set the user-provided Zhipu and DeepSeek keys only in root `.env`, set `AGENT_PROVIDER=failover`, and set model IDs from the approved design. Confirm `git check-ignore .env` succeeds and `git diff` contains no key fragments.

## Task 2: Structured Online Providers and Three-Level Failover

**Files:**
- Create: `backend/app/agents/prompts.py`
- Create: `backend/app/agents/redaction.py`
- Create: `backend/app/agents/openai_compatible.py`
- Create: `backend/app/agents/failover.py`
- Modify: `backend/app/agents/service.py`
- Test: `backend/tests/agents/test_redaction.py`
- Test: `backend/tests/agents/test_openai_compatible.py`
- Test: `backend/tests/agents/test_failover.py`

- [ ] **Step 1: Write RED tests for PII redaction**

```python
def test_redact_external_model_input():
    text = "电话13800138000，邮箱student@example.com，身份证11010519491231002X"
    assert redact_pii(text) == "电话[PHONE]，邮箱[EMAIL]，身份证[ID_CARD]"
```

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/agents/test_redaction.py -q`

- [ ] **Step 2: Implement deterministic redaction and verify GREEN**

Use compiled regular expressions for mainland mobile numbers, email addresses, and 18-character identity numbers. Recursively redact strings inside dictionaries and lists before request serialization.

- [ ] **Step 3: Write RED provider contract tests with `httpx.MockTransport`**

Assert the client sends `model`, system/user messages, `response_format={"type":"json_object"}`, and redacted inputs to `/chat/completions`, then validates response content into the requested Pydantic contract and overwrites `provider` with the actual provider/model label.

- [ ] **Step 4: Implement `OpenAICompatibleAgentGateway` and prompts**

Use one generic `_invoke(operation, inputs, contract)` implementation and the seven existing gateway methods. Do not add an SDK dependency; use existing `httpx` so Zhipu and DeepSeek share the same transport and test surface.

- [ ] **Step 5: Write RED failover tests**

Create five focused tests named `test_primary_success_does_not_call_secondary`, `test_rate_limit_uses_secondary`, `test_invalid_primary_json_uses_secondary`, `test_both_online_providers_fail_uses_local`, and `test_three_failures_open_provider_circuit`. Each test uses concrete fake gateways with call counters and asserts the returned provider label plus exact call counts.

- [ ] **Step 6: Implement retry, circuit breaker, and local fallback**

Retry only transport failures, 429, and 5xx once. Do not retry authentication or other 4xx errors. Keep circuit state behind a clock abstraction so tests do not sleep. Preserve the actual provider label in the validated result.

- [ ] **Step 7: Wire `build_agent_gateway()` and verify all Agent tests**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/agents -q`

Expected: existing FastGPT/local tests and new failover tests all pass.

## Task 3: pgvector Schema, Durable AI Tasks, and Media Metadata

**Files:**
- Create: `backend/app/ai/__init__.py`
- Create: `backend/app/ai/models.py`
- Create: `backend/app/ai/service.py`
- Create: `backend/app/ai/schemas.py`
- Modify: `backend/app/core/model_registry.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/alembic/versions/9f12c3a4b5d6_local_ai_runtime.py`
- Test: `backend/tests/ai/test_tasks.py`
- Test: `backend/tests/ai/test_models.py`

- [ ] **Step 1: Write RED task state tests**

Test enqueue, owner isolation, `queued -> running -> succeeded`, retry scheduling, max-attempt failure, expired lease reclamation, and cancellation. Use the project SQLite fixture while keeping PostgreSQL locking in the production query.

- [ ] **Step 2: Implement AI task models and state transitions**

Use enums for task type/status, JSON text fields consistent with the existing project, UTC timestamps, attempt count, lease expiration, and sanitized errors. Claim with `with_for_update(skip_locked=True)` and update the lease in the same transaction.

- [ ] **Step 3: Add document and media models**

Define `DocumentChunk.embedding` as `Vector(1024)` with a JSON variant under SQLite tests. Define `MediaArtifact` with owner, session, media type, storage path, size, expiry, and creation fields.

- [ ] **Step 4: Add `pgvector` dependency and Alembic migration**

The migration executes `CREATE EXTENSION IF NOT EXISTS vector`, creates all `ai_tasks` columns defined in Task 3 Step 2, creates all `document_chunks` and `media_artifacts` columns defined in Task 3 Step 3, and uses `Vector(1024)` for the PostgreSQL embedding column.

Add indexes for queue claiming, owner/status lookup, source lookup, expiry cleanup, and an HNSW cosine index after initial data volume permits it. The downgrade removes application tables but does not drop the shared `vector` extension.

- [ ] **Step 5: Run migration and model tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ai/test_tasks.py tests/ai/test_models.py -q
.\.venv\Scripts\alembic.exe upgrade head
```

Expected: tests pass and the local SQLite development database migrates without losing existing records.

## Task 4: Local Embedding, OCR, and Speech Service Contracts

**Files:**
- Create: `services/embedding/app.py`
- Create: `services/embedding/requirements.txt`
- Create: `services/embedding/Dockerfile`
- Create: `services/ocr/app.py`
- Create: `services/ocr/requirements.txt`
- Create: `services/ocr/Dockerfile`
- Create: `services/speech/app.py`
- Create: `services/speech/requirements.txt`
- Create: `services/speech/Dockerfile`
- Create: `services/tests/test_service_contracts.py`

- [ ] **Step 1: Write RED HTTP contract tests in fake-model mode**

Each app exposes `/health/live`, `/health/ready`, and its inference endpoints. Fake mode must exercise validation and response structure without downloading weights.

Expected contracts:

```json
POST /embed {"texts":["数据分析岗位"]}
Response fields: `model="BAAI/bge-m3"`, `dimensions=1024`, and `vectors` containing one 1024-element finite float array.

POST /ocr multipart file
{"pages":[{"page":1,"text":"掌握 Python 和 SQL","confidence":0.98}],"text":"掌握 Python 和 SQL"}

POST /transcribe multipart file
{"text":"我完成了销售数据分析项目","duration_seconds":3.2,"model":"paraformer-zh"}

POST /synthesize {"text":"请介绍你的项目经历","language":"ZH"}
audio/wav
```

- [ ] **Step 2: Implement lazy model loaders and health states**

Load models once per service process under a lock. `live` is immediate; `ready` is false until the model is loaded or fake mode is active. Never download a model during module import.

- [ ] **Step 3: Implement BGE-M3 CPU inference**

Resolve the model through ModelScope cache, then use:

```python
model = BGEM3FlagModel(model_path, use_fp16=False, devices=["cpu"])
vectors = model.encode(
    texts,
    batch_size=4,
    max_length=512,
    return_dense=True,
    return_sparse=False,
    return_colbert_vecs=False,
)["dense_vecs"]
```

Validate that every output has exactly 1024 finite floats.

- [ ] **Step 4: Implement forced PDF OCR**

Initialize `PaddleOCR(lang="ch", ocr_version="PP-OCRv5", device="cpu")`. Use `predict()` or `predict_iter()` over the uploaded PDF, extract `rec_texts` and `rec_scores`, preserve page ordering, and compute a page confidence mean. Limit files and page counts.

- [ ] **Step 5: Implement non-streaming FunASR and MeloTTS**

Install FFmpeg in the image. Convert uploads to 16kHz mono WAV. Initialize:

```python
AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
    device="cuda",
)
```

Use `generate(input=wav_path, batch_size_s=60)`. Initialize MeloTTS with `TTS(language="ZH", device="cpu")` and synthesize with speaker `ZH`. Guard both endpoints with one process lock.

- [ ] **Step 6: Run service contract tests and container builds**

Run fake-mode pytest first, then build each image independently. Expected: contract tests pass and all three Docker images build.

## Task 5: Internal Clients, Worker, and Forced Resume OCR Pipeline

**Files:**
- Create: `backend/app/ai/clients.py`
- Create: `backend/app/ai/worker.py`
- Modify: `backend/app/resumes/router.py`
- Modify: `backend/app/resumes/parser.py`
- Modify: `backend/app/resumes/models.py`
- Modify: `backend/app/resumes/schemas.py`
- Test: `backend/tests/ai/test_clients.py`
- Test: `backend/tests/ai/test_worker.py`
- Modify: `backend/tests/resumes/test_upload.py`

- [ ] **Step 1: Write RED internal-client tests**

Use `httpx.MockTransport` to verify timeouts, multipart files, response validation, non-2xx mapping, and that internal errors never expose response bodies containing source text.

- [ ] **Step 2: Implement typed internal clients**

Provide `embed(texts)`, `ocr(path)`, `transcribe(path)`, and `synthesize(text)` methods with Pydantic response models and bounded timeouts.

- [ ] **Step 3: Change PDF upload behavior with RED tests**

Assert PDF upload stores the file, returns `parse_status="queued"` plus `task_id`, and does not call the old `fitz` text parser. Assert DOCX still parses locally but queues embedding.

- [ ] **Step 4: Implement worker handlers**

Handlers must be idempotent:

- `resume_ocr`: call OCR, update parsed text and status, enqueue `document_embedding`.
- `document_embedding`: chunk content, call BGE-M3, replace chunks in one transaction, mark resume parsed.
- `speech_transcription`: call FunASR and store transcript in task result.
- `speech_synthesis`: call MeloTTS, store random WAV file, create media artifact, return artifact ID.

- [ ] **Step 5: Implement worker loop and recovery**

Poll at the configured interval, claim one task, dispatch by enum, heartbeat long operations, and use signal-aware shutdown. A failed task is rescheduled or finalized according to attempt count.

- [ ] **Step 6: Verify pipeline tests**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/ai tests/resumes -q`

## Task 6: Semantic Job Retrieval

**Files:**
- Create: `backend/app/jobs/retrieval.py`
- Modify: `backend/app/jobs/router.py`
- Modify: `backend/app/core/seed.py`
- Test: `backend/tests/jobs/test_retrieval.py`

- [ ] **Step 1: Write RED retrieval tests**

Test deterministic text chunking, owner/class filters, cosine ordering, top-k bounds, and the response shape of `/jobs/recommended`. Under SQLite, inject a distance function or repository fake; add a PostgreSQL integration test for actual `cosine_distance()`.

- [ ] **Step 2: Implement chunk persistence and retrieval**

Hash chunks to avoid unnecessary re-embedding. Query PostgreSQL with:

```python
select(DocumentChunk)
    .where(DocumentChunk.source_type == "job")
    .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
    .limit(limit)
```

- [ ] **Step 3: Add recommended jobs endpoint and seed indexing**

Use the confirmed profile summary as the query text. Return job fields plus semantic score; leave existing five-dimensional match endpoint intact. Seed startup enqueues missing job embeddings idempotently.

- [ ] **Step 4: Verify job tests**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/jobs -q`

## Task 7: Voice Interview Tasks and Authorized Media

**Files:**
- Create: `backend/app/ai/router.py`
- Modify: `backend/app/interviews/router.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/scheduler.py`
- Test: `backend/tests/interviews/test_voice.py`
- Test: `backend/tests/ai/test_media.py`

- [ ] **Step 1: Write RED authorization and lifecycle tests**

Cover authenticated task reads, owner-only retries, recording MIME/size checks, session ownership, transcription task creation, artifact download authorization, and expired file cleanup.

- [ ] **Step 2: Implement task and capability APIs**

Return task ID/type/status/result/error/attempt timestamps without internal file paths. Capability output reports configured provider/model and local service readiness but never key values.

- [ ] **Step 3: Implement transcription endpoint**

Accept WebM/Ogg/WAV recording uploads for an active owned interview session, store with a random name, and enqueue `speech_transcription`. The answer endpoint continues to accept only user-confirmed text.

- [ ] **Step 4: Queue follow-up speech and secure blob download**

When an evaluation contains a follow-up, enqueue `speech_synthesis` and return its task ID. Media download checks owner and expiry before `FileResponse`.

- [ ] **Step 5: Add seven-day cleanup job and verify tests**

Delete expired files and metadata without following symlinks outside the configured media directory. Run the focused AI/interview tests.

## Task 8: Resume Status and Recorded Voice Frontend

**Files:**
- Modify: `frontend/src/app/api.ts`
- Modify: `frontend/src/features/student/ResumePage.tsx`
- Modify: `frontend/src/features/student/InterviewPage.tsx`
- Create: `frontend/src/features/student/ResumePage.test.tsx`
- Create: `frontend/src/features/student/InterviewVoice.test.tsx`
- Modify: `frontend/e2e/student-flow.spec.ts`

- [ ] **Step 1: Write RED resume status component tests**

Mock upload returning a queued task, then mock polling through OCR and embedding to parsed. Assert accessible Chinese status text and retry action on failure.

- [ ] **Step 2: Implement resume polling UI**

Use TanStack Query `refetchInterval` only while pending work exists. Keep dimensions stable and show queued, OCR, embedding, parsed, and failed states.

- [ ] **Step 3: Write RED voice interaction tests**

Mock `MediaRecorder`, microphone permission rejection, transcription task completion, editable transcript, answer submission, TTS task completion, and authenticated audio blob retrieval.

- [ ] **Step 4: Implement recording and playback**

Use familiar record/stop/play icons with tooltips and accessible labels. Keep text input visible at all times. Revoke object URLs on replacement/unmount and stop microphone tracks after recording.

- [ ] **Step 5: Extend Playwright flow**

Use a deterministic audio fixture and browser permissions. Verify recording fallback, transcript editing, submission, provider source, and follow-up playback controls without horizontal overflow at desktop and 390x844.

- [ ] **Step 6: Run frontend tests, lint, and build**

```powershell
cd frontend
npm test -- --run
npm run lint
npm run build
```

## Task 9: Docker GPU Deployment and One-Click Startup

**Files:**
- Modify: `docker-compose.yml`
- Create: `.dockerignore`
- Modify: `backend/Dockerfile`
- Modify: `start-docker.bat`
- Modify: `scripts/verify.ps1`
- Modify: `README.md`
- Modify: `docs/test-report.md`

- [ ] **Step 1: Add Compose services and pgvector image**

Use a PostgreSQL 17 pgvector image compatible with the existing data directory. Add worker, embedding, OCR, and speech services, internal health checks, model cache volumes, media volume, and NVIDIA device reservation only for speech.

- [ ] **Step 2: Add build-context exclusions**

Exclude `.git`, worktrees, local virtual environments, `node_modules`, test artifacts, databases, uploads, model caches, and `.env` so frontend context is not hundreds of megabytes.

- [ ] **Step 3: Make startup secret-safe and model-aware**

`start-docker.bat` verifies Docker/NVIDIA runtime, required key presence, Compose validity, and final capabilities. It must never echo key values. During model download it prints service/model status rather than treating `starting` as failure too early.

- [ ] **Step 4: Preserve and migrate current PostgreSQL data**

Create a backup, bring the stack down without `-v`, switch the image, start the database, apply Alembic, and verify counts for users/jobs/application records match pre-migration counts.

- [ ] **Step 5: Update operational documentation**

Document first model download, cache volumes, GPU requirements, API failover labels, task retry, audio retention, backups, and stop/start commands. Update the stale Docker limitation in the test report.

## Task 10: Full Verification and Real-Service Acceptance

**Files:**
- Modify: `docs/test-report.md`
- Create/update: `docs/test-artifacts/` screenshots and sanitized logs

- [ ] **Step 1: Run all non-container checks**

Run `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1 -SkipContainers` and require zero failures.

- [ ] **Step 2: Build and start the complete Compose stack**

Run `docker compose up --build -d`. Wait on conditions, not fixed sleeps, until database/backend/frontend/worker and model services reach their defined ready state.

- [ ] **Step 3: Verify real model services**

- Encode Chinese text with BGE-M3 and assert 1024 finite values.
- OCR a generated one-page Chinese PDF and inspect recognized text/confidence.
- Transcribe a deterministic Chinese WAV with FunASR.
- Synthesize and inspect non-empty playable WAV with MeloTTS.
- Record peak GPU usage and confirm no OOM.

- [ ] **Step 4: Verify provider paths without logging secrets**

Call a minimal structured operation with Zhipu. Force the primary URL to a controlled failure and verify DeepSeek returns a valid contract. Force both online clients to fail and verify `local-demo` is shown.

- [ ] **Step 5: Run full browser E2E and visual checks**

Run Playwright against `http://127.0.0.1:8080` at desktop/mobile sizes. Inspect screenshots, console errors, network failures, text overflow, recording controls, and audio element state.

- [ ] **Step 6: Security and persistence checks**

- Search tracked files, image history, Compose config output, and logs for key fragments.
- Restart containers and verify cached models avoid re-download.
- Restart Worker during a leased task and verify recovery.
- Verify existing demo data counts and uploaded persistent files remain.

- [ ] **Step 7: Update the test report with exact evidence**

Record versions, test counts, service health, model IDs, download/cache state, API provider outcomes, GPU peak, limitations, and artifact paths. Do not record credentials or raw resume/audio content.
