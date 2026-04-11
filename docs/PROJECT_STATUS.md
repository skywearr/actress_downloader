# Project Status

Last updated: 2026-04-11

This document is intended as long-lived project context for future iterations, including future LLM sessions. It records what has already been built, which product decisions have been made, what is still missing, and what should happen next.

## Current Product Scope

The current repository is an adult-catalog metadata MVP, not a downloader.

Current supported flow:

1. Input a performer name or alias
2. Resolve the performer identity
3. Discover related work codes
4. Generate tags for each work
5. Persist structured metadata into PostgreSQL
6. Export one local sidecar metadata file per work

Explicitly out of scope for the current MVP:

- Torrent search
- Thunder download integration
- Download task management
- Resource scheduling / retry queue
- Full web scraping from real catalog sites

## Product Decisions Already Made

The following decisions should be treated as current project direction unless explicitly changed later:

- Phase 1 only covers metadata collection and tagging. Download features are intentionally postponed.
- PostgreSQL is the default and preferred database. SQLite is not part of the current plan.
- The preferred database name is fixed to `actress_downloader`.
- If the PostgreSQL account has `CREATEDB` privilege, initialization should create the database automatically.
- If the account does not have `CREATEDB` privilege, the user may manually create a database and pass `--database-name`.
- A single work may contain multiple performers. The schema and sidecar format must preserve that.
- LangGraph is the orchestration layer, but a linear fallback pipeline is kept so the project can still run without LangGraph at runtime.
- LLM tagging currently uses an adult-catalog-oriented prompt, but the accepted output is still filtered through the repository's derived candidate tags before persistence.
- The current default remote LLM provider is xAI, using the Responses API.

## Implemented Features

### 1. Pipeline and orchestration

Implemented in:

- [src/actress_downloader/graph.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/graph.py)
- [src/actress_downloader/pipeline.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/pipeline.py)

Status:

- LangGraph pipeline is implemented with the following nodes:
  - `normalize_input`
  - `resolve_identity`
  - `discover_works`
  - `tag_works`
  - `persist_works`
  - `export_sidecars`
- A linear fallback pipeline is implemented for environments where LangGraph is unavailable.

### 2. Identity resolution and offline work discovery

Implemented in:

- [src/actress_downloader/connectors/seed.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/connectors/seed.py)
- [examples/demo_catalog.json](/C:/Users/94611/PyCharmMiscProject/actress_downloader/examples/demo_catalog.json)

Status:

- The current connector is an offline seed connector for MVP development.
- It supports alias-based identity matching.
- It supports fuzzy matching when there is no exact alias match.
- It supports discovering works that contain the target performer.
- It supports works with multiple performers.

Important limitation:

- This is not a real network connector and does not fetch live metadata.

### 3. PostgreSQL schema and persistence

Implemented in:

- [sql/init_schema.sql](/C:/Users/94611/PyCharmMiscProject/actress_downloader/sql/init_schema.sql)
- [src/actress_downloader/storage.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/storage.py)
- [scripts/init_db.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/scripts/init_db.py)

Status:

- PostgreSQL schema is implemented.
- Automatic database creation is implemented.
- Schema initialization is implemented.
- Upsert logic is implemented for:
  - performers
  - performer aliases
  - works
  - work-performer relations
  - tags
  - work-tag relations
  - raw source records

Current schema supports:

- stable performer identities
- alias history
- multi-performer works
- normalized tags
- raw source payload snapshots

### 4. Local sidecar metadata export

Implemented in:

- [src/actress_downloader/sidecar.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/sidecar.py)

Status:

- One sidecar file is exported per work:
  - `library/<work_code>/metadata.json`
- Sidecar files include:
  - work code
  - title
  - release date
  - studio
  - series
  - all credited performers
  - normalized tags
  - raw tags
  - source info
  - synopsis
  - extra payload

### 5. Tagging system

Implemented in:

- [src/actress_downloader/tagging.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/tagging.py)
- [src/actress_downloader/llm.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/llm.py)

Status:

- A rule-based tagger is implemented.
- An LLM-based enrichment layer is implemented.
- Rule tags currently include stable structural metadata such as:
  - `studio:*`
  - `series:*`
  - `year:*`
  - `performer-group:*`
  - `performer-count:*`
- LLM enrichment currently runs through an adult-catalog-oriented prompt, while accepted persisted tags are still limited to derived candidate labels such as:
  - `quality:*`
  - `format:*`
  - `edition:*`
  - `cast:*`
  - `collection:*`
  - `release-era:*`

### 6. Current LLM request strategy

Implemented in:

- [src/actress_downloader/llm.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/llm.py)
- [src/actress_downloader/config.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/config.py)
- [config/settings.toml](/C:/Users/94611/PyCharmMiscProject/actress_downloader/config/settings.toml)

Status:

- xAI is the current default provider.
- xAI now uses the Responses API instead of the older chat-completions-compatible path.
- The prompt is currently written for an adult-catalog tagging workflow.
- The xAI request includes `web_search` as a tool.
- The xAI request includes `store = false`.
- The request payload still avoids sending title text, synopsis text, and performer names into the model payload.
- Full request / stream / final output logging is preserved for debugging.

Important note:

- Even though the prompt wording is adult-catalog-oriented, the runtime currently only persists tags that survive candidate-tag filtering in code.

### 7. Configuration

Implemented in:

- [src/actress_downloader/config.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/config.py)
- [config/settings.toml](/C:/Users/94611/PyCharmMiscProject/actress_downloader/config/settings.toml)

Status:

- PostgreSQL host / port / username / password are configurable.
- LLM provider / model / API key / timeout / base URL are configurable.
- The fixed default database name is `actress_downloader`.
- Provider-specific API key resolution is implemented.

### 8. CLI entrypoint

Implemented in:

- [src/actress_downloader/cli.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/cli.py)

Status:

- CLI supports:
  - performer name input
  - optional config path
  - optional seed file path
  - optional manual database name override
  - optional sidecar output root override
- The CLI prints resolved performer, aliases, provider/model, discovered works, and tags.

### 9. Tests

Implemented in:

- [tests/test_seed_connector.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_seed_connector.py)
- [tests/test_sidecar.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_sidecar.py)
- [tests/test_config.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_config.py)
- [tests/test_tagging.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_tagging.py)
- [tests/test_llm_prompt.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_llm_prompt.py)

Recent local verification:

- `python -m compileall src tests` passed
- `python -m unittest tests.test_seed_connector tests.test_sidecar tests.test_config tests.test_tagging tests.test_llm_prompt` passed

## Not Implemented Yet

The following items are still pending:

- Real online catalog connector
- Real alias discovery from live sources
- Automatic discovery of all historical names from live sources
- Full live work discovery from real metadata sites
- Download workflow
- Torrent search
- Thunder integration
- Download state tracking
- Retry / resume / dedup queue for downloads
- Interactive manual review flow inside CLI or UI
- Incremental synchronization
- Conflict resolution across multiple upstream sources
- Background task scheduling
- Full online smoke test of the latest xAI Responses API path after the current prompt/runtime alignment work

## Known Issues and Caveats

### 1. The current connector is still demo-only

Even though the pipeline architecture is real, the data source is still seeded from a local JSON file.

### 2. The Python environment needs cleanup

Current known environment issue:

- `.venv` points to an unavailable Python 3.12 interpreter path and should be rebuilt.

Practical consequence:

- The latest verification was run with the currently available system Python, not the broken `.venv` interpreter entrypoint.

### 3. README content quality

The current README contains mojibake / encoding noise from earlier edits and should be cleaned up in a future maintenance pass.

### 4. Python version metadata should be revisited

Current files:

- [pyproject.toml](/C:/Users/94611/PyCharmMiscProject/actress_downloader/pyproject.toml)
- [.python-version](/C:/Users/94611/PyCharmMiscProject/actress_downloader/.python-version)

Observation:

- `.python-version` points to `3.12`
- `pyproject.toml` currently says `>=3.11,<3.14`
- Local validation recently ran under the available system Python 3.14 executable because the 3.12 virtual environment entrypoint is broken

This mismatch should be cleaned up before more serious runtime validation.

## Recommended Next Steps

The safest next sequence is:

1. Rebuild the local Python 3.12 virtual environment and re-install dependencies
2. Run a live smoke test for the current xAI Responses API flow
3. Replace the seed connector with a real metadata connector
4. Add a manual review step for ambiguous identity resolution
5. Decide whether richer tag semantics should come from:
   - more deterministic local rules, or
   - a more permissive LLM strategy

## Short Summary For Future LLM Sessions

If you are a future LLM working on this repository, the most important facts are:

- This is currently a metadata MVP, not a downloader.
- PostgreSQL is already integrated and should remain the default.
- The database name should remain `actress_downloader` unless the user explicitly overrides it for a manual setup.
- Multi-performer works are already supported and must continue to be supported.
- The current live-data source is not implemented yet; the seed connector is only a placeholder.
- LLM tagging currently uses an adult-catalog-oriented prompt, while persisted output is still filtered by candidate tags in code.
- xAI is the current default provider and is expected to use the Responses API path.
- The next valuable work is environment repair plus a real connector, not more polishing of the seed-only MVP.
