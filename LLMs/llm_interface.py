from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Classification:
    is_relevant: bool
    matched_interest: str
    reasoning: str


class LLMError(Exception):
    """An LLM call failed after retries (network, quota, blocked response...)."""


class LLMInterface(ABC):

    @abstractmethod
    def classify(self, title: str, abstract: str) -> Classification:
        """Decide from title + abstract whether the paper is relevant."""

    def classify_batch(self, papers: list[tuple[str, str]]) -> list[Classification]:
        """Return verdicts in input order. Providers can group requests."""
        return [self.classify(title, abstract) for title, abstract in papers]

    @abstractmethod
    def summarize(self, title: str, matched_interest: str, paper_text: str) -> str:
        """Produce an HTML summary of a relevant paper."""
