import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from google import genai
from google.genai import errors, types

import config
import main
from arxiv_client import ArxivClient, Paper
from emailer import DigestEntry, RunStats, build_digest
from LLMs.gemini import Gemini
from LLMs.llm_interface import LLMError


class GeminiTests(unittest.TestCase):
    def setUp(self):
        with patch.object(config, "genai_api_token", "test-key"):
            self.bot = Gemini()
        self.addCleanup(self.bot.client.close)

    def test_sdk_parses_batched_verdicts_and_restores_order(self):
        def respond(request):
            self.assertIn(config.classifier_model, request.url.path)
            payload = json.loads(request.content)
            inputs = json.loads(payload["contents"][0]["parts"][0]["text"])
            self.assertEqual([p["paper_id"] for p in inputs], [0, 1])
            verdicts = [
                {"paper_id": i, "is_relevant": bool(i), "matched_interest": "Depth" if i else "none",
                 "reasoning": "test"} for i in (1, 0)
            ]
            return httpx.Response(200, json={"candidates": [{"content": {
                "role": "model", "parts": [{"text": json.dumps(verdicts)}]}, "finishReason": "STOP"}]})
        with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
            with genai.Client(api_key="test-key", http_options=types.HttpOptions(
                    httpx_client=http_client)) as client, patch.object(self.bot, "client", client):
                verdicts = self.bot.classify_batch([("first", "abstract"), ("second", "abstract")])
        self.assertEqual([v.is_relevant for v in verdicts], [False, True])

    def test_invalid_or_duplicate_results_do_not_match_the_wrong_paper(self):
        verdict = SimpleNamespace(paper_id=0, reasoning="test", matched_interest="none", is_relevant=False)
        for result in ([verdict, verdict], [verdict], None):
            with self.subTest(result=result), patch.object(
                    self.bot, "_generate", return_value=SimpleNamespace(parsed=result)):
                with self.assertRaises(LLMError):
                    self.bot.classify_batch([("a", ""), ("b", "")])

    def test_daily_quota_exhaustion_stops_further_calls_to_that_model(self):
        limit = {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}
        api_error = errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "details": [limit]}})
        with patch.object(self.bot, "client") as client:
            client.models.generate_content.side_effect = api_error
            for _ in range(2):
                with self.assertRaises(LLMError):
                    self.bot.classify("paper", "abstract")
            client.models.generate_content.assert_called_once()


class DigestTests(unittest.TestCase):
    def test_followed_author_after_classifier_quota_failure(self):
        papers = [Paper(str(i), title=str(i)) for i in range(3)]
        papers.append(Paper("3", authors=[config.followed_authors[0].upper()]))
        stats = RunStats()
        llm = Mock()
        llm.classify_batch.side_effect = LLMError("quota")
        with patch.object(config, "classifier_batch_size", 1), patch.object(
                config, "max_consecutive_llm_failures", 1), patch("main.summarize_paper") as summarize:
            with self.assertLogs(level="ERROR"):
                entries = main.process_papers(llm, Mock(), papers, stats)
        llm.classify_batch.assert_called_once()
        self.assertEqual((len(entries), stats.unclassified, stats.scanned, stats.relevant), (1, 3, 1, 1))
        self.assertEqual(summarize.call_args.args[2], papers[3])
        self.assertTrue(stats.aborted_reason)

    def test_summary_html_allows_only_digest_formatting(self):
        entry = DigestEntry(Paper("1", title="<title>"),
                            '<b>Why</b><br /><img alt="outside"><i>yes</i>', "Depth")
        body = build_digest("today", [entry], RunStats(1, 1))
        self.assertIn("<b>Why</b><br />", body)
        self.assertIn("<i>yes</i>", body)
        self.assertNotIn("<img", body)
        self.assertIn("&lt;title&gt;", body)

    def test_arxiv_failure_returns_failure_and_suppresses_empty_email(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(main, "__file__", str(Path(tmp) / "main.py")), \
                patch.object(sys, "argv", ["main.py"]), patch("main.setup_logging"), \
                patch("main.config.validate"), patch("main.Gemini"), patch("main.ArxivClient") as client, \
                patch("main.send_email") as send:
            client.return_value.fetch_papers_from_feed.side_effect = RuntimeError("unavailable")
            client.return_value.fetch_paper_ids.side_effect = RuntimeError("unavailable")
            with self.assertLogs(level="WARNING"):
                self.assertEqual(main.main(), 1)
            send.assert_not_called()

    def test_metadata_partial_failure_delivers_marked_digest_and_nonzero_exit(self):
        paper = Paper("1", title="Example", authors=[config.followed_authors[0]])
        with tempfile.TemporaryDirectory() as tmp, patch.object(main, "__file__", str(Path(tmp) / "main.py")), \
                patch.object(sys, "argv", ["main.py", "--date", "Fri, 20 Nov 2026", "--limit", "2"]), \
                patch("main.setup_logging"), patch("main.config.validate"), patch("main.Gemini") as llm, \
                patch("main.ArxivClient") as client, patch("main.extract_text_and_figure", return_value=("", None)), \
                patch("main.send_email") as send:
            client.return_value.fetch_paper_ids.return_value = ["1", "2", "3"]
            client.return_value.fetch_metadata.return_value = [paper]
            llm.return_value.summarize.return_value = "<b>Summary</b>"
            with self.assertLogs(level="ERROR"):
                self.assertEqual(main.main(), 1)
            client.return_value.fetch_metadata.assert_called_once_with(["1", "2"])
            subject, html, entries = send.call_args.args
            self.assertTrue(subject.startswith("[Incomplete]"))
            self.assertIn("Unclassified papers: 1", html)
            self.assertEqual(entries[0].paper, paper)

    def test_feed_with_only_replacements_has_an_announcement_date(self):
        feed = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:a="http://arxiv.org/schemas/atom">
          <entry><published>2026-11-20T00:00:00-05:00</published><a:announce_type>replace</a:announce_type></entry>
        </feed>'''
        client = ArxivClient()
        with patch.object(client, "_get", return_value=Mock(content=feed)):
            self.assertEqual(client.fetch_papers_from_feed("cs.CV"), ("Fri, 20 Nov 2026", []))
