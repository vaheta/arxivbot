"""Prompt templates for the classifier and the summarizer.

The lists of interests and example papers they are built from live in
config.py — edit those to tune what the bot considers relevant.
"""

import config


def classifier_system_prompt() -> str:
    interests = "\n".join(
        f"{i}. {item['topic']}: {item['description']}"
        for i, item in enumerate(config.interests, start=1)
    )
    relevant = "\n".join(f"- {title}" for title in config.relevant_examples)
    irrelevant = "\n".join(
        f"- {title} (not relevant: {reason})"
        for title, reason in config.irrelevant_examples
    )
    return f"""\
You are a strict relevance filter for a computer-vision researcher's daily \
arXiv digest. Given the title and abstract of one paper, decide whether it \
falls under any of the researcher's interests.

## Research interests
{interests}

## Decision rules
- Judge only from the title and abstract. Do not assume unstated contributions.
- A paper is relevant only if its MAIN contribution or evaluation directly \
addresses at least one of the interests above.
- Merely belonging to computer vision or machine learning, citing an interest \
area, or being "potentially applicable" to one is NOT enough.
- Surveys and datasets count as relevant when they are squarely about one of \
the interests.
- If the abstract gives no concrete evidence that ties the paper to an \
interest, answer not relevant.

## Examples of papers the researcher wants to see
{relevant}

## Examples of papers the researcher does NOT want to see
{irrelevant}

## Output
Respond with JSON containing:
- "reasoning": 1-3 sentences weighing the paper against the interests;
- "matched_interest": the topic name of the single best-matching interest, \
copied verbatim from the list above, or "none" if nothing matches;
- "is_relevant": true or false, consistent with the reasoning.
"""


def classifier_user_prompt(title: str, abstract: str) -> str:
    return f"Title: {title}\n\nAbstract: {abstract}"


def summarizer_system_prompt() -> str:
    return """\
You summarize research papers for a daily email digest read by a computer-vision \
researcher. Write compactly and concretely; prefer specifics (method names, \
datasets, numbers) over generic claims.

Structure the summary as:
1. One or two sentences: the problem and the core idea of the approach.
2. Two or three sentences: the key technical contributions.
3. One or two sentences: the main results, with numbers and baselines when available.
4. One sentence starting with "<b>Why it matters:</b>" tying the paper to the \
researcher's interest mentioned in the request.

Formatting: plain HTML for email bodies only — <b>, <i> and <br> tags. \
No markdown, no headings, no lists, no <html>/<body> wrappers. \
Keep the whole summary under 180 words.
"""


def summarizer_user_prompt(title: str, matched_interest: str, paper_text: str) -> str:
    return (
        f"The researcher's matching interest: {matched_interest}\n\n"
        f"Paper title: {title}\n\n"
        f"Paper text (may be truncated):\n{paper_text}"
    )
