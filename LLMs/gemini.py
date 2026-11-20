import json
import logging
import time

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

import config
import prompts
from LLMs.llm_interface import Classification, LLMError, LLMInterface

RETRYABLE_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


class _RelevanceVerdict(BaseModel):
    paper_id: int
    reasoning: str
    matched_interest: str
    is_relevant: bool


def _daily_quota_exhausted(error: errors.APIError) -> bool:
    if not isinstance(error.details, dict):
        return False
    details = error.details.get("error", {}).get("details", [])
    return any("perday" in violation.get("quotaId", "").lower()
               for detail in details for violation in detail.get("violations", []))


class Gemini(LLMInterface):

    def __init__(self):
        self.client = genai.Client(
            api_key=config.genai_api_token,
            http_options=types.HttpOptions(timeout=120_000,
                                           retry_options=types.HttpRetryOptions(attempts=1)),
        )
        self._unavailable_models = {}
        self._classifier_system_prompt = prompts.classifier_system_prompt()
        self._summarizer_system_prompt = prompts.summarizer_system_prompt()
        self._last_call_time = {}  # model name -> monotonic timestamp

    def classify(self, title: str, abstract: str) -> Classification:
        return self.classify_batch([(title, abstract)])[0]

    def classify_batch(self, papers: list[tuple[str, str]]) -> list[Classification]:
        if not papers:
            return []
        contents = [{"paper_id": i, "title": title, "abstract": abstract}
                    for i, (title, abstract) in enumerate(papers)]
        response = self._generate(
            model=config.classifier_model,
            requests_per_minute=config.classifier_requests_per_minute,
            contents=json.dumps(contents, ensure_ascii=False),
            generation_config=types.GenerateContentConfig(
                system_instruction=self._classifier_system_prompt,
                response_mime_type="application/json",
                response_schema=list[_RelevanceVerdict],
            ),
        )
        verdicts = response.parsed
        if not isinstance(verdicts, list) or len(verdicts) != len(papers):
            raise LLMError("Classifier did not return one verdict per paper")
        by_id = {v.paper_id: Classification(v.is_relevant, v.matched_interest, v.reasoning)
                 for v in verdicts}
        if set(by_id) != set(range(len(papers))):
            raise LLMError("Classifier returned missing, duplicate or unknown paper IDs")
        return [by_id[i] for i in range(len(papers))]

    def summarize(self, title: str, matched_interest: str, paper_text: str) -> str:
        response = self._generate(
            model=config.summarizer_model,
            requests_per_minute=config.summarizer_requests_per_minute,
            contents=prompts.summarizer_user_prompt(title, matched_interest, paper_text),
            generation_config=types.GenerateContentConfig(
                system_instruction=self._summarizer_system_prompt,
            ),
        )
        if not response.text:
            raise LLMError("Summarizer returned an empty response")
        return response.text.strip()

    def _generate(self, model, requests_per_minute, contents, generation_config):
        """Call the API with rate limiting and retries on transient errors."""
        if model in self._unavailable_models:
            raise LLMError(self._unavailable_models[model])
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._throttle(model, requests_per_minute)
            try:
                return self.client.models.generate_content(
                    model=model, contents=contents, config=generation_config,
                )
            except errors.APIError as e:
                last_error = e
                reason = f"{e.status} {e.code}"
                if e.code in (401, 403, 404) or (e.code == 429 and _daily_quota_exhausted(e)):
                    self._unavailable_models[model] = f"{model} unavailable for this run ({reason})"
                    raise LLMError(self._unavailable_models[model]) from e
                retryable = e.code in RETRYABLE_CODES
            except httpx.HTTPError as e:  # connection/timeout problems
                last_error = e
                retryable = True
                reason = type(e).__name__
            if not retryable or attempt == MAX_ATTEMPTS:
                break
            delay = min(15 * 2 ** (attempt - 1), 120)
            logging.warning("%s from %s (attempt %d/%d), retrying in %ds",
                            reason, model, attempt, MAX_ATTEMPTS, delay)
            time.sleep(delay)
        raise LLMError(f"{model} call failed: {reason}") from last_error

    def _throttle(self, model: str, requests_per_minute: int) -> None:
        interval = 60.0 / requests_per_minute
        wait = interval - (time.monotonic() - self._last_call_time.get(model, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_call_time[model] = time.monotonic()
