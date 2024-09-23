from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# arXiv.org section for parsing. Default is Computer Vision and Pattern Recognition
arxiv_section = "cs.CV"

# Prompt texts
interests = [
    "Multimodal vision like RGB+Depth or RGB+Polarization including detection/segmentation/depth and other tasks", 
    "Stereo reconstruction", 
    "6DOF object pose detection",
    "Robotics vision",
    "Human body keypoint detection and pose estimation",
    "Polarization",
    "Single-view depth and multi-view depth",
    "Transparent object detection/segmentation or depth estimation"
]

prompt_interests_check = (
    "My research interests are: {research_interests}. Does the following research paper fall under any of my research interests? "
    "Answer with 'Yes' or 'No' without any additional details: {text}"
)

prompt_summary_request = (
    "Please send me a summary of the paper. Use HTML formatting (<b> for bold, <i> for italic, <br> for change of line and so on). Don't use markdown formatting. "
    "In the end add a very short explanation on why you decided that this article is relevant to me."
)

prompt_why_no = (
    "Explain why no?"
)

# Email configuration
email_from = os.getenv("EMAIL_FROM")
email_to = os.getenv("EMAIL_TO")
email_smtp_server = os.getenv("EMAIL_SMTP_SERVER")
email_smtp_port = int(os.getenv("EMAIL_SMTP_PORT"))
email_username = os.getenv("EMAIL_USERNAME")
email_password = os.getenv("EMAIL_PASSWORD")

# Gemini LLM configuration
model_name = "gemini-1.5-flash"
genai_api_token = os.getenv("GENAI_API_TOKEN")
generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 4096,
  "response_mime_type": "text/plain",
}
safety_settings = [
  {
    "category": "HARM_CATEGORY_HARASSMENT",
    "threshold": "BLOCK_ONLY_HIGH",
  },
  {
    "category": "HARM_CATEGORY_HATE_SPEECH",
    "threshold": "BLOCK_ONLY_HIGH",
  },
  {
    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "threshold": "BLOCK_ONLY_HIGH",
  },
  {
    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
    "threshold": "BLOCK_ONLY_HIGH",
  },
]