from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from actress_downloader.config import LLMConfig
from actress_downloader.timing import emit_timing_event, now
from actress_downloader.utils import normalize_text


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AliasExpansionRequest:
    payload: dict[str, Any]
    response_format: str


class PerformerAliasExpander(Protocol):
    def expand_aliases(self, query_name: str) -> list[str]:
        """Return additional searchable aliases for a performer query."""


class NoOpPerformerAliasExpander:
    def expand_aliases(self, query_name: str) -> list[str]:
        return []


class RemotePerformerAliasExpander:
    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def expand_aliases(self, query_name: str) -> list[str]:
        normalized_query = query_name.strip()
        if not normalized_query or not self._config.is_active:
            return []

        try:
            import httpx
        except ImportError:
            logger.warning("Alias expansion skipped because httpx is not installed.")
            return []

        request = _build_alias_expansion_request(
            query_name=normalized_query,
            provider=self._config.provider,
            model=self._config.model,
            temperature=self._config.alias_lookup_temperature,
        )

        started_at = now()
        status_code: int | None = None
        alias_count = 0
        error_type = ""
        try:
            response = httpx.post(
                self._config.base_url,
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                json=request.payload,
                timeout=self._config.timeout_seconds,
            )
            status_code = response.status_code
            response.raise_for_status()
        except Exception as exc:
            error_type = type(exc).__name__
            logger.warning("Alias expansion request failed for %s: %s", normalized_query, exc)
            return []

        try:
            aliases = _parse_alias_response(
                response_json=response.json(),
                response_format=request.response_format,
            )
            cleaned_aliases = _clean_aliases(aliases, normalized_query)
            alias_count = len(cleaned_aliases)
            return cleaned_aliases
        except Exception as exc:
            error_type = type(exc).__name__
            logger.warning("Alias expansion response parsing failed for %s: %s", normalized_query, exc)
            return []
        finally:
            emit_timing_event(
                "llm.alias_lookup",
                started_at,
                provider=self._config.provider,
                model=self._config.model,
                query_name=normalized_query,
                status_code=status_code,
                alias_count=alias_count,
                error_type=error_type or None,
            )


def build_alias_expander(config: LLMConfig) -> PerformerAliasExpander:
    provider = config.provider.strip().lower()
    if provider in {"glm", "xai"}:
        return RemotePerformerAliasExpander(config)
    return NoOpPerformerAliasExpander()


def _build_alias_expansion_request(
    query_name: str,
    provider: str,
    model: str,
    temperature: float,
) -> AliasExpansionRequest:
    system_prompt = (
        "You resolve JAV performer identities for a metadata pipeline. "
        "Your job is strict alias recall, not fuzzy brainstorming. "
        "Return only alternate searchable names that refer to the exact same performer as the input query. "
        "Allowed outputs are limited to: exact Japanese full names, exact kana variants, exact romaji or English transliterations, "
        "reversed word-order transliterations, and strongly verified former stage names. "
        "Reject candidates that only share a surname, only share a given name, only look phoneticly similar, or belong to a different person. "
        "If you are not confident that a name is the same performer, omit it. "
        "If web_search is available, verify before returning former names. "
        "When uncertain, return an empty aliases list. "
        "Return JSON only."
    )
    user_prompt = json.dumps(
        {
            "task": "Find alternate searchable performer names for JavBus lookup.",
            "query_name": query_name,
            "output_schema": {
                "aliases": ["search string 1", "search string 2"],
            },
            "rules": [
                "Return a JSON object with a single aliases array.",
                "Include at most 6 names.",
                "Do not include explanations.",
                "Do not invent unsupported aliases.",
                "Do not include studios, titles, labels, or unrelated people.",
                "Do not include people that merely share a surname or given name.",
                "Do not include approximate matches like Aya Mikami for Yua Mikami.",
                "Prefer precision over recall.",
            ],
        },
        ensure_ascii=False,
    )

    normalized_provider = provider.strip().lower()
    if normalized_provider == "xai":
        return AliasExpansionRequest(
            payload={
                "model": model,
                "temperature": temperature,
                "store": False,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "tools": [{"type": "web_search"}],
            },
            response_format="responses",
        )

    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if normalized_provider == "glm":
        payload["thinking"] = {"type": "disabled"}
    return AliasExpansionRequest(
        payload=payload,
        response_format="chat_completions",
    )


def _parse_alias_response(response_json: dict[str, Any], response_format: str) -> list[str]:
    if response_format == "responses":
        content = _extract_responses_output_text(response_json)
    else:
        content = _extract_chat_completions_output_text(response_json)
    return _parse_alias_list(content)


def _extract_chat_completions_output_text(response_json: dict[str, Any]) -> str:
    for choice in response_json.get("choices", []):
        if not isinstance(choice, dict):
            continue
        message = choice.get("message", {})
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def _extract_responses_output_text(response_json: dict[str, Any]) -> str:
    output_text = response_json.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output_items = response_json.get("output", [])
    if not isinstance(output_items, list):
        return ""

    chunks: list[str] = []
    for item in output_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content_items = item.get("content", [])
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") in {"output_text", "text"}:
                text_value = content_item.get("text")
                if isinstance(text_value, str):
                    chunks.append(text_value)
    return "".join(chunks)


def _parse_alias_list(content: str) -> list[str]:
    stripped = content.strip()
    if not stripped:
        return []

    candidates = [_try_extract_aliases(stripped)]
    match = re.search(r"\{[\s\S]*\}", stripped)
    if match:
        candidates.append(_try_extract_aliases(match.group(0)))
    match = re.search(r"\[[\s\S]*\]", stripped)
    if match:
        candidates.append(_try_extract_aliases(match.group(0)))

    for candidate_aliases in candidates:
        if candidate_aliases:
            return candidate_aliases
    return []


def _try_extract_aliases(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, dict):
        aliases = parsed.get("aliases")
        if isinstance(aliases, list):
            return [str(item) for item in aliases if str(item).strip()]
        return []

    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]

    return []


def _clean_aliases(values: list[str], query_name: str) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = {normalize_text(query_name)}
    for value in values:
        cleaned = value.strip()
        normalized = normalize_text(cleaned)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(cleaned)
    return deduped[:8]
