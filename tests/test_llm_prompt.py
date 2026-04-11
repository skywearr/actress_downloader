from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.domain import PerformerCredit, WorkRecord
from actress_downloader.llm import _build_safe_tagging_request


class LLMPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = WorkRecord(
            code="TEST-100",
            title="Should Not Be Sent To The Model",
            release_date="2024-07-12",
            studio="S1",
            series="Collaboration Stage",
            performers=[
                PerformerCredit(canonical_name="Performer A"),
                PerformerCredit(canonical_name="Performer B"),
            ],
            raw_tags=["HD", "Drama", "UnmappedTag"],
            synopsis="Should Not Be Sent To The Model",
        )

    def test_xai_request_uses_responses_api_shape_and_safe_context(self) -> None:
        request = _build_safe_tagging_request(
            work=self.work,
            existing_tags=["studio:s1"],
            provider="xai",
            model="grok-4.20",
            temperature=0.2,
        )

        self.assertEqual("responses", request.stream_format)
        self.assertIn("quality:hd", request.candidate_tags)
        self.assertIn("genre:drama", request.candidate_tags)
        self.assertIn("cast:duo", request.candidate_tags)
        self.assertIn("cast:ensemble", request.candidate_tags)
        self.assertIn("collection:series-entry", request.candidate_tags)
        self.assertIn("release-era:2020s", request.candidate_tags)
        self.assertTrue(request.payload["stream"])
        self.assertFalse(request.payload["store"])
        self.assertEqual([{"type": "web_search"}], request.payload["tools"])
        self.assertNotIn("messages", request.payload)

        user_content = request.payload["input"][1]["content"]
        decoded = json.loads(user_content)

        self.assertEqual("TEST-100", decoded["catalog_context"]["code"])
        self.assertEqual(2, decoded["catalog_context"]["performer_count"])
        self.assertEqual(["HD", "Drama"], decoded["catalog_context"]["safe_raw_tags"])
        self.assertIn("candidate_tag_options", decoded)
        self.assertNotIn("title", decoded["catalog_context"])
        self.assertNotIn("synopsis", decoded["catalog_context"])
        self.assertNotIn("performers", decoded["catalog_context"])
        self.assertNotIn("Performer A", user_content)
        self.assertNotIn("Performer B", user_content)

        system_prompt = request.payload["input"][0]["content"]
        self.assertIsInstance(system_prompt, str)
        self.assertTrue(system_prompt)
        self.assertIn("web_search", system_prompt)
        self.assertIn("existing_tags", system_prompt)
        self.assertIn("JSON", system_prompt)

    def test_glm_request_keeps_chat_completions_shape(self) -> None:
        request = _build_safe_tagging_request(
            work=self.work,
            existing_tags=["studio:s1"],
            provider="glm",
            model="glm-4.7",
            temperature=0.2,
        )

        self.assertEqual("chat_completions", request.stream_format)
        self.assertIn("messages", request.payload)
        self.assertNotIn("tools", request.payload)
        self.assertEqual({"type": "disabled"}, request.payload["thinking"])


if __name__ == "__main__":
    unittest.main()
