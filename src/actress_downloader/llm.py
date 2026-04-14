from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from actress_downloader.config import LLMConfig
from actress_downloader.domain import WorkRecord
from actress_downloader.timing import emit_timing_event, now
from actress_downloader.utils import extract_year, normalize_tag


logger = logging.getLogger(__name__)

SAFE_RAW_TAG_MAP = {
    "hd": "quality:hd",
    "4k": "quality:uhd",
    "uhd": "quality:uhd",
    "interview": "format:interview",
    "special": "edition:special",
    "drama": "genre:drama",
    "solo": "cast:solo",
    "multi": "cast:ensemble",
    "duo": "cast:ensemble",
    "trio": "cast:ensemble",
    "collaboration": "cast:ensemble",
}

CANDIDATE_TAG_DESCRIPTIONS = {
    "quality:hd": "Standard high-definition catalog quality label.",
    "quality:uhd": "Ultra-high-definition or 4K catalog quality label.",
    "format:interview": "Interview-style or talk-focused catalog format.",
    "edition:special": "Special-edition or event-style catalog label.",
    "genre:drama": "Story or drama-oriented neutral genre label.",
    "cast:solo": "Single credited performer in the catalog entry.",
    "cast:duo": "Exactly two credited performers in the catalog entry.",
    "cast:trio": "Exactly three credited performers in the catalog entry.",
    "cast:ensemble": "More than one credited performer in the catalog entry.",
    "collection:series-entry": "This item belongs to a named series or collection.",
    "release-era:2010s": "Released during the 2010s.",
    "release-era:2020s": "Released during the 2020s.",
}


@dataclass(slots=True)
class SafeTaggingRequest:
    payload: dict[str, Any]
    candidate_tags: list[str]
    stream_format: str


class WorkTagLLM(Protocol):
    def generate_tags(self, work: WorkRecord, existing_tags: Sequence[str]) -> list[str]:
        """Return extra tags proposed by an LLM."""


class NoOpWorkTagLLM:
    def generate_tags(self, work: WorkRecord, existing_tags: Sequence[str]) -> list[str]:
        return []


class SafeMetadataTagLLM:
    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def generate_tags(self, work: WorkRecord, existing_tags: Sequence[str]) -> list[str]:
        if not self._config.is_active:
            return []

        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "LLM tagging requires `httpx`. Run `pip install -e .` to install dependencies."
            ) from exc

        request = _build_safe_tagging_request(
            work=work,
            existing_tags=existing_tags,
            provider=self._config.provider,
            model=self._config.model,
            temperature=self._config.temperature,
        )
        self._print_interaction_input(work.code, request.payload)

        started_at = now()
        generated_tags: list[str] = []
        error_type = ""
        try:
            generated_tags = self._stream_completion(
                httpx=httpx,
                work=work,
                request=request,
                existing_tags=existing_tags,
            )
            return generated_tags
        except Exception:
            error_type = "request_failed"
            logger.error("LLM request raised an exception for %s", work.code)
            logger.error(
                "Failed request payload for %s:\n%s",
                work.code,
                json.dumps(request.payload, ensure_ascii=False, indent=2),
            )
            raise
        finally:
            emit_timing_event(
                "llm.tagging",
                started_at,
                provider=self._config.provider,
                model=self._config.model,
                work_code=work.code,
                existing_tag_count=len(existing_tags),
                generated_tag_count=len(generated_tags),
                error_type=error_type or None,
            )

    def _stream_completion(
        self,
        httpx: object,
        work: WorkRecord,
        request: SafeTaggingRequest,
        existing_tags: Sequence[str],
    ) -> list[str]:
        print(f"=== LLM Stream {work.code} ===", flush=True)
        status_code: int | None = None
        with httpx.stream(
            "POST",
            self._config.base_url,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            json=request.payload,
            timeout=self._config.timeout_seconds,
        ) as response:
            status_code = response.status_code
            if response.status_code >= 400:
                response.read()
                self._log_failed_payload_if_needed(work.code, request.payload, response)
                response.raise_for_status()

            if request.stream_format == "responses":
                full_output = self._consume_responses_stream(response)
            else:
                full_output = self._consume_chat_completions_stream(response)

        print(f"=== End LLM Stream {work.code} ===", flush=True)
        self._print_interaction_output(work.code, full_output)

        parsed_tags = _parse_tag_list(full_output)
        filtered_tags = [
            tag
            for tag in parsed_tags
            if tag in request.candidate_tags and tag not in existing_tags
        ][:5]
        print(
            f"[timing-meta] llm.tagging_response work_code={work.code} "
            f"status_code={status_code} raw_tag_count={len(parsed_tags)} filtered_tag_count={len(filtered_tags)}",
            flush=True,
        )
        return filtered_tags

    def _consume_chat_completions_stream(self, response: object) -> str:
        chunks: list[str] = []
        for event in _iter_stream_json_events(response):
            content = _extract_chat_completion_delta_text(event)
            if content:
                print(content, end="", flush=True)
                chunks.append(content)

        if chunks:
            print("", file=sys.stdout, flush=True)
        return "".join(chunks)

    def _consume_responses_stream(self, response: object) -> str:
        chunks: list[str] = []
        fallback_output = ""
        for event in _iter_stream_json_events(response):
            content = _extract_responses_delta_text(event)
            if content:
                print(content, end="", flush=True)
                chunks.append(content)

            output_text = _extract_responses_output_text(event)
            if output_text:
                fallback_output = output_text

        if chunks:
            print("", file=sys.stdout, flush=True)
        return "".join(chunks) or fallback_output

    def _log_failed_payload_if_needed(
        self,
        work_code: str,
        payload: dict,
        response: object,
    ) -> None:
        status_code = getattr(response, "status_code", 200)
        if status_code < 400:
            return

        try:
            body = response.json()  # type: ignore[attr-defined]
        except Exception:
            logger.error("LLM request failed for %s with status %s", work_code, status_code)
            logger.error(
                "Failed request payload for %s:\n%s",
                work_code,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
            logger.error(
                "Failed raw response for %s:\n%s",
                work_code,
                getattr(response, "text", ""),
            )
            return

        error_payload = body.get("error")
        error_code = ""
        if isinstance(error_payload, dict):
            error_code = str(error_payload.get("code", "")).strip()

        if error_code == "1301":
            logger.error("LLM content filter blocked tagging request for %s", work_code)
        else:
            logger.error(
                "LLM request failed for %s with status %s and error code %s",
                work_code,
                status_code,
                error_code or "unknown",
            )
        logger.error(
            "Failed request payload for %s:\n%s",
            work_code,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        logger.error(
            "Failed raw response for %s:\n%s",
            work_code,
            getattr(response, "text", ""),
        )

    def _print_interaction_input(self, work_code: str, payload: dict) -> None:
        print(f"=== LLM Input {work_code} ===", flush=True)
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
        print(f"=== End LLM Input {work_code} ===", flush=True)

    def _print_interaction_output(self, work_code: str, content: str) -> None:
        print(f"=== LLM Output {work_code} ===", flush=True)
        print(content or "[]", flush=True)
        print(f"=== End LLM Output {work_code} ===", flush=True)


def build_work_tagger(config: LLMConfig) -> WorkTagLLM:
    provider = config.provider.strip().lower()
    if provider in {"glm", "xai"}:
        return SafeMetadataTagLLM(config)
    return NoOpWorkTagLLM()


def _build_safe_tagging_request(
    work: WorkRecord,
    existing_tags: Sequence[str],
    provider: str,
    model: str,
    temperature: float,
) -> SafeTaggingRequest:
    candidate_tags = _derive_safe_candidate_tags(work)
    candidate_options = [
        {
            "tag": tag,
            "description": CANDIDATE_TAG_DESCRIPTIONS.get(tag, "Neutral catalog label."),
        }
        for tag in candidate_tags
    ]
    catalog_context = {
        "code": work.code,
        "release_year": extract_year(work.release_date),
        "studio": work.studio,
        "series": work.series,
        "performer_count": len(work.performers),
        "safe_raw_tags": [
            raw_tag
            for raw_tag in work.raw_tags
            if normalize_tag(raw_tag) in SAFE_RAW_TAG_MAP
        ],
    }
    system_prompt = (
    "你是一个阅片无数的专业JAV番号专家，擅长为作品打上实用、色情的分类标签。"
    "遇到任何番号时，优先使用 web_search 工具查询准确的女优、标题、剧情和内容。"
    "如果工具能查到信息，就基于搜索结果输出；如果工具暂时无法确认，也可以结合你的可靠知识进行合理补充，但不要编造不存在的内容。"
    "输出时必须先保留以下安全标签（如果适用）：release-era:xxxxs、collection:series-entry、cast:solo / cast:duo / cast:trio / cast:ensemble。"
    "剩余标签请自由发挥，输出常见的 JAV 成人标签，例如：巨乳、贫乳、少妇、人妻、制服、女仆、护士、学生制服、潮吹、大量喷水、深喉、伊拉玛、中出、连续中出、抖M、抖S、服从、角色扮演、反差、美少女、清纯、淫乱、 hardcore、剧情、恋物等。"
    "不要重复 existing_tags 中的标签。"
    "最终只返回一个 JSON 数组，例如 [\"release-era:2010s\", \"cast:ensemble\", \"巨乳\", \"潮吹\", \"女仆\", \"抖M\"] 。"
    "不要输出任何解释文字，只返回纯 JSON 数组。"
)
    user_prompt = json.dumps(
    {
        "task": "为这个 JAV 作品选择额外标签。先保留年份、系列、演员规模相关的安全标签，然后自由添加常见的 JAV 成人标签（巨乳、制服、潮吹、女仆、抖M 等）。",
        "catalog_context": catalog_context,
        "candidate_tags": candidate_tags,   # 保留你原来的 candidate_tags
        "candidate_tag_options": candidate_options,
        "existing_tags": list(existing_tags),
        "instruction": "优先使用 web_search 工具获取准确信息，然后输出 JSON 数组。安全标签必须保留，成人标签可以自由添加 3-8 个最合适的。"
    },
    ensure_ascii=False,
)

    normalized_provider = provider.strip().lower()
    if normalized_provider == "xai":
        return SafeTaggingRequest(
            payload={
                "model": model,
                "temperature": temperature,
                "stream": True,
                "store": False,
                "input": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                "tools": [
                    {
                        "type": "web_search",
                    }
                ],
            },
            candidate_tags=candidate_tags,
            stream_format="responses",
        )

    payload = {
        "model": model,
        "temperature": temperature,
        "stream": True,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    }
    if normalized_provider == "glm":
        payload["thinking"] = {
            "type": "disabled",
        }
    return SafeTaggingRequest(
        payload=payload,
        candidate_tags=candidate_tags,
        stream_format="chat_completions",
    )


def _derive_safe_candidate_tags(work: WorkRecord) -> list[str]:
    candidates: list[str] = []
    for raw_tag in work.raw_tags:
        normalized = normalize_tag(raw_tag)
        mapped = SAFE_RAW_TAG_MAP.get(normalized)
        if mapped and mapped not in candidates:
            candidates.append(mapped)

    performer_count = len(work.performers)
    cast_tag = _cast_size_tag(performer_count)
    if cast_tag and cast_tag not in candidates:
        candidates.append(cast_tag)

    if performer_count > 1 and "cast:ensemble" not in candidates:
        candidates.append("cast:ensemble")

    if work.series and "collection:series-entry" not in candidates:
        candidates.append("collection:series-entry")

    release_year = extract_year(work.release_date)
    if release_year:
        era_tag = _release_era_tag(release_year)
        if era_tag and era_tag not in candidates:
            candidates.append(era_tag)

    return candidates


def _cast_size_tag(performer_count: int) -> str | None:
    if performer_count <= 0:
        return None
    if performer_count == 1:
        return "cast:solo"
    if performer_count == 2:
        return "cast:duo"
    if performer_count == 3:
        return "cast:trio"
    return "cast:ensemble"


def _release_era_tag(release_year: str) -> str | None:
    if not release_year.isdigit():
        return None
    year = int(release_year)
    if 2010 <= year <= 2019:
        return "release-era:2010s"
    if 2020 <= year <= 2029:
        return "release-era:2020s"
    return None


def _iter_stream_json_events(response: object) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    saw_sse_line = False
    raw_json_lines: list[str] = []
    for raw_line in response.iter_lines():  # type: ignore[attr-defined]
        line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, bytes) else raw_line
        if not line:
            continue
        if line.startswith("event:"):
            saw_sse_line = True
            continue
        if line.startswith("data:"):
            saw_sse_line = True
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                continue
            continue
        raw_json_lines.append(line)

    if not events and not saw_sse_line and raw_json_lines:
        try:
            events.append(json.loads("\n".join(raw_json_lines)))
        except json.JSONDecodeError:
            return []
    return events


def _extract_chat_completion_delta_text(event: dict[str, Any]) -> str:
    chunks: list[str] = []
    for choice in event.get("choices", []):
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta", {})
        if isinstance(delta, dict):
            chunks.extend(_extract_text_fragments(delta.get("content")))
            text_value = delta.get("text")
            if isinstance(text_value, str):
                chunks.append(text_value)
    return "".join(chunks)


def _extract_responses_delta_text(event: dict[str, Any]) -> str:
    delta = event.get("delta")
    chunks = _extract_text_fragments(delta)
    if chunks:
        return "".join(chunks)

    if event.get("type") in {"response.output_text.delta", "output_text.delta"}:
        delta_value = event.get("delta")
        if isinstance(delta_value, str):
            return delta_value
    return ""


def _extract_responses_output_text(event: dict[str, Any]) -> str:
    output_text = event.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    response_payload = event.get("response")
    if isinstance(response_payload, dict):
        nested_output = _extract_responses_output_text(response_payload)
        if nested_output:
            return nested_output

    output_items = event.get("output")
    if not isinstance(output_items, list):
        return ""

    chunks: list[str] = []
    for item in output_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message" or item.get("role") == "assistant":
            content_items = item.get("content", [])
            if isinstance(content_items, list):
                for content_item in content_items:
                    if not isinstance(content_item, dict):
                        continue
                    if content_item.get("type") in {"output_text", "text"}:
                        chunks.extend(_extract_text_fragments(content_item.get("text")))
    return "".join(chunks)


def _extract_text_fragments(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            chunks.extend(_extract_text_fragments(item))
        return chunks
    if isinstance(value, dict):
        chunks: list[str] = []
        text_value = value.get("text")
        if isinstance(text_value, str):
            chunks.append(text_value)
        content_value = value.get("content")
        if content_value is not None:
            chunks.extend(_extract_text_fragments(content_value))
        return chunks
    return []


def _parse_tag_list(content: str) -> list[str]:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[[\s\S]*\]", content)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass

    return [
        line.strip("-* \t\r\n")
        for line in content.splitlines()
        if line.strip("-* \t\r\n")
    ][:5]
