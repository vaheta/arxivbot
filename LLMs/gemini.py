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
    reasoning: str
    matched_interest: str
    is_relevant: bool


class Gemini(LLMInterface):

    def __init__(self):
        self.client = genai.Client(api_key=config.genai_api_token)
        self._classifier_system_prompt = prompts.classifier_system_prompt()
        self._summarizer_system_prompt = prompts.summarizer_system_prompt()
        self._last_call_time = {}  # model name -> monotonic timestamp

    def classify(self, title: str, abstract: str) -> Classification:
        response = self._generate(
            model=config.classifier_model,
            requests_per_minute=config.classifier_requests_per_minute,
            contents=prompts.classifier_user_prompt(title, abstract),
            generation_config=types.GenerateContentConfig(
                system_instruction=self._classifier_system_prompt,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=_RelevanceVerdict,
            ),
        )
        verdict = response.parsed
        if verdict is None:
            raise LLMError(f"Classifier returned unparseable output: {response.text!r:.200}")
        return Classification(
            is_relevant=verdict.is_relevant,
            matched_interest=verdict.matched_interest,
            reasoning=verdict.reasoning,
        )

    def summarize(self, title: str, matched_interest: str, paper_text: str) -> str:
        response = self._generate(
            model=config.summarizer_model,
            requests_per_minute=config.summarizer_requests_per_minute,
            contents=prompts.summarizer_user_prompt(title, matched_interest, paper_text),
            generation_config=types.GenerateContentConfig(
                system_instruction=self._summarizer_system_prompt,
                temperature=0.4,
            ),
        )
        if not response.text:
            raise LLMError("Summarizer returned an empty response")
        return response.text.strip()

    def _generate(self, model, requests_per_minute, contents, generation_config):
        """Call the API with rate limiting and retries on transient errors."""
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._throttle(model, requests_per_minute)
            try:
                return self.client.models.generate_content(
                    model=model, contents=contents, config=generation_config,
                )
            except errors.APIError as e:
                last_error = e
                retryable = e.code in RETRYABLE_CODES
                reason = f"{e.status} {e.code}"
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
        raise LLMError(f"{model} call failed: {last_error}") from last_error

    def _throttle(self, model: str, requests_per_minute: int) -> None:
        interval = 60.0 / requests_per_minute
        wait = interval - (time.monotonic() - self._last_call_time.get(model, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_call_time[model] = time.monotonic()
