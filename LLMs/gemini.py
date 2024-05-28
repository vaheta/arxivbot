import google.generativeai as genai
import config
from LLMs.llm_interface import LLMInterface
from typing import Tuple

class Gemini(LLMInterface):

    def __init__(self):
        genai.configure(api_key=config.genai_api_token)
        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            safety_settings=config.safety_settings,
            generation_config=config.generation_config,
        )

    def analyze_text(self, text: str) -> Tuple[bool, str]:
        chat_session = self.model.start_chat(history=[])
        prompt_interests_check = config.prompt_interests_check.format(research_interests=', '.join(config.interests), text=text)
        response = chat_session.send_message(prompt_interests_check)
        if "yes" in response.text.lower():
            summary_response = chat_session.send_message(config.prompt_summary_request)
            return True, summary_response.text
        else:
            response = chat_session.send_message(config.prompt_why_no)
            return False, response.text
