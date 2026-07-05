from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# arXiv settings
# ---------------------------------------------------------------------------

# arXiv.org section for parsing. Default is Computer Vision and Pattern Recognition
arxiv_section = "cs.CV"

# Politeness delay between consecutive requests to arxiv.org (seconds).
# arXiv asks automated clients to keep at least 3 seconds between API calls.
arxiv_request_delay = 3.0

# Maximum number of characters of PDF text sent to the summarizer.
# Keeps token usage bounded for very long papers (appendices, references, ...).
max_pdf_chars = 60_000

# ---------------------------------------------------------------------------
# Followed authors
# ---------------------------------------------------------------------------
# Any paper with one of these names among its authors is added to the digest
# automatically, without going through the relevance classifier. Names must
# match how they appear on arXiv (case-insensitive).

followed_authors = [
    "Kaiming He",
    "Achuta Kadambi",
    "Sergey Levine",
]

# ---------------------------------------------------------------------------
# Research interests
# ---------------------------------------------------------------------------
# Each interest has a short topic name and a description that tells the
# classifier what does (and does not) belong to it. Be as concrete as you can:
# the classifier only sees the title and abstract of each paper.

interests = [
    {
        "topic": "Stereo reconstruction",
        "description": (
            "Stereo matching and disparity estimation, multi-view stereo, "
            "active or event-based stereo, stereo benchmarks and datasets."
        ),
    },
    {
        "topic": "6DOF object pose estimation",
        "description": (
            "Instance- or category-level 6D object pose estimation and tracking, "
            "CAD/model-based or model-free pose, pose refinement, novel-object pose, "
            "object pose for grasping and manipulation."
        ),
    },
    {
        "topic": "Vision for robotics and VLA models",
        "description": (
            "Vision-language-action (VLA) models, robot manipulation policies learned "
            "from visual input, imitation or reinforcement learning for manipulation, "
            "robot perception for grasping, assembly and bin picking."
        ),
    },
    {
        "topic": "Polarization imaging",
        "description": (
            "Shape from polarization, polarimetric cameras and sensors, polarization "
            "cues for depth, surface normals, reflectance separation, or perceiving "
            "transparent and specular objects."
        ),
    },
    {
        "topic": "Single-view and multi-view depth estimation",
        "description": (
            "Monocular depth estimation, multi-view depth, depth foundation models, "
            "metric depth, depth completion from sparse measurements."
        ),
    },
    {
        "topic": "General 3D reconstruction and feed-forward reconstruction models",
        "description": (
            "3D scene reconstruction: structure-from-motion, multi-view stereo "
            "pipelines, neural scene representations, and especially feed-forward "
            "reconstruction models that directly predict point maps, depth and "
            "cameras — VGGT and anything building on it, DUSt3R/MASt3R-style "
            "approaches, large reconstruction models."
        ),
    },
    {
        "topic": "Positional encodings for transformers",
        "description": (
            "Positional encoding schemes for transformers, both within images "
            "(2D RoPE, relative position encodings, resolution extrapolation) and "
            "in 3D (camera ray or camera pose encodings, epipolar or other "
            "geometry-aware attention biases)."
        ),
    },
    {
        "topic": "World models",
        "description": (
            "World models: action- or camera-conditioned video prediction and "
            "generation used as learned simulators, interactive world models for "
            "robotics and embodied agents, controllable scene simulation."
        ),
    },
    {
        "topic": "High-resolution transformer inference",
        "description": (
            "Techniques that make transformers/ViTs efficient at high image "
            "resolutions: token pruning or merging, tiling and windowed attention, "
            "sparse or linear attention, multi-scale processing, memory-efficient "
            "inference for large inputs."
        ),
    },
    {
        "topic": "Agentic vision",
        "description": (
            "Multimodal or vision-language agents that plan, call tools, or act "
            "(in GUIs, browsers, simulators or the real world), active perception, "
            "visual reasoning through iterative actions."
        ),
    },
]

# Titles of papers that are good examples of what you WANT to receive.
# They anchor the classifier; 4-8 well-chosen titles work well.
relevant_examples = [
    "FoundationPose: Unified 6D Pose Estimation and Tracking of Novel Objects",
    "SAM-6D: Segment Anything Model Meets Zero-Shot 6D Object Pose Estimation",
    "FoundationStereo: Zero-Shot Stereo Matching",
    "Depth Anything V2",
    "OpenVLA: An Open-Source Vision-Language-Action Model",
    "Deep Shape from Polarization: Learning to Estimate Surface Normals",
    "VGGT: Visual Geometry Grounded Transformer",
    "Cosmos World Foundation Model Platform for Physical AI",
]

# Titles of papers you do NOT want, with a short reason. These teach the
# classifier where the boundary is (generic computer vision is not enough).
irrelevant_examples = [
    ("High-Resolution Image Synthesis with Latent Diffusion Models",
     "image generation, no 3D perception or robotics contribution"),
    ("A Survey on Face Recognition under Occlusion",
     "biometrics, outside all interests"),
    ("nnU-Net-based Brain Tumor Segmentation in Multimodal MRI",
     "medical image segmentation, outside all interests"),
    ("Vision Transformers for Video Action Recognition",
     "video understanding, outside all interests"),
    ("Scene Text Detection and Recognition in the Wild",
     "OCR / document analysis, outside all interests"),
]

# ---------------------------------------------------------------------------
# LLM settings (Gemini)
# ---------------------------------------------------------------------------
# Two models are used to stay inside the free tier:
#  - the classifier runs once per paper (hundreds of calls/day), so it uses the
#    lightweight model with the highest free-tier daily quota;
#  - the summarizer runs only for relevant papers (a handful of calls/day), so
#    it can afford the stronger model.
# Free-tier quotas as of mid-2026: gemini-3.1-flash-lite ~15 RPM / 1000 RPD,
# gemini-3.5-flash has lower daily caps. Check https://aistudio.google.com/rate-limit
# for the live numbers of your project.

genai_api_token = os.getenv("GENAI_API_TOKEN")

classifier_model = "gemini-3.1-flash-lite"
classifier_requests_per_minute = 12  # keep a margin below the 15 RPM free limit

summarizer_model = "gemini-3.5-flash"
summarizer_requests_per_minute = 8

# Abort the run if this many LLM calls fail in a row (e.g. daily quota
# exhausted); whatever was classified so far is still emailed.
max_consecutive_llm_failures = 5

# ---------------------------------------------------------------------------
# Email settings
# ---------------------------------------------------------------------------

email_from = os.getenv("EMAIL_FROM")
email_to = os.getenv("EMAIL_TO")
email_smtp_server = os.getenv("EMAIL_SMTP_SERVER")
email_smtp_port = int(os.getenv("EMAIL_SMTP_PORT") or 587)
email_username = os.getenv("EMAIL_USERNAME")
email_password = os.getenv("EMAIL_PASSWORD")


def validate(require_email: bool = True) -> None:
    """Fail fast with a clear message when required settings are missing."""
    required = {"GENAI_API_TOKEN": genai_api_token}
    if require_email:
        required.update({
            "EMAIL_FROM": email_from,
            "EMAIL_TO": email_to,
            "EMAIL_SMTP_SERVER": email_smtp_server,
            "EMAIL_USERNAME": email_username,
            "EMAIL_PASSWORD": email_password,
        })
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing)}. "
            "Copy .env_template to .env and fill them in."
        )
