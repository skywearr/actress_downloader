# Project Context

This repository keeps its current implementation status and iteration notes in:

- [docs/PROJECT_STATUS.md](/C:/Users/94611/PyCharmMiscProject/actress_downloader/docs/PROJECT_STATUS.md)

Read that file first before starting a new iteration.

Short version:

- This is currently a metadata MVP, not a downloader.
- PostgreSQL integration, schema initialization, LangGraph orchestration, sidecar export, and multi-performer support are already implemented.
- The current connector is still an offline seed connector and should be replaced with a real metadata source in a future iteration.
- LLM tagging currently uses an adult-catalog-oriented prompt, while persisted output is still filtered through candidate tags in code.
- The next high-value work is repairing the Python 3.12 environment and then validating the xAI Responses API path with a real smoke test.
