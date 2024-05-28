from abc import ABC, abstractmethod
from typing import Tuple

class LLMInterface(ABC):

    @abstractmethod
    def analyze_text(self, text: str) -> Tuple[bool, str]:
        pass
