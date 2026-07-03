import argparse
import html
import logging
import os
from datetime import datetime

import config
from arxiv_client import ArxivClient, extract_text_and_figure
from emailer import DigestEntry, RunStats, build_digest, send_email
from LLMs.gemini import Gemini
from LLMs.llm_interface import LLMError, LLMInterface


def setup_logging(logfile_path: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(logfile_path), logging.StreamHandler()],
    )


def summarize_paper(llm: LLMInterface, client: ArxivClient, paper, matched_interest: str,
                    stats: RunStats) -> DigestEntry:
    """Download the PDF and summarize a relevant paper.

    Falls back to the abstract when the PDF or the summarizer fails, so a
    relevant paper always makes it into the digest.
    """
    text, figure = "", None
    try:
        text, figure = extract_text_and_figure(client.fetch_pdf(paper))
    except Exception as e:
        logging.warning("PDF processing failed for %s: %s", paper.arxiv_id, e)

    try:
        summary = llm.summarize(paper.title, matched_interest, text or paper.abstract)
    except LLMError as e:
        logging.error("Summarization failed for %s: %s", paper.arxiv_id, e)
        stats.errors += 1
        summary = f"{html.escape(paper.abstract)}<br><i>(automatic summary failed, abstract shown)</i>"

    return DigestEntry(paper=paper, summary_html=summary,
                       matched_interest=matched_interest, figure_png=figure)


def process_papers(llm: LLMInterface, client: ArxivClient, papers, stats: RunStats):
    """Classify every paper from its abstract; summarize only the relevant ones."""
    entries = []
    consecutive_failures = 0
    for idx, paper in enumerate(papers, start=1):
        try:
            verdict = llm.classify(paper.title, paper.abstract)
            consecutive_failures = 0
        except LLMError as e:
            logging.error("[%d/%d] classification failed for %s: %s",
                          idx, len(papers), paper.arxiv_id, e)
            stats.errors += 1
            consecutive_failures += 1
            if consecutive_failures >= config.max_consecutive_llm_failures:
                stats.aborted_reason = (
                    f"{consecutive_failures} LLM calls failed in a row "
                    f"(quota exhausted?); {len(papers) - idx} papers not scanned."
                )
                logging.error(stats.aborted_reason)
                break
            continue

        stats.scanned += 1
        decision = "YES" if verdict.is_relevant else "no "
        logging.info("[%d/%d] %s %s | %s", idx, len(papers), decision,
                     paper.title, verdict.reasoning)

        if verdict.is_relevant:
            stats.relevant += 1
            entries.append(summarize_paper(llm, client, paper, verdict.matched_interest, stats))
    return entries


def main():
    parser = argparse.ArgumentParser(description="Daily arXiv digest bot")
    parser.add_argument("--date", help="Listing date to process, e.g. 'Fri, 3 Jul 2026' "
                                       "(default: today)")
    parser.add_argument("--limit", type=int, help="Only process the first N papers (for testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Do not send the email; write the digest HTML next to the log instead")
    args = parser.parse_args()

    today = datetime.now()
    date = args.date or today.strftime("%a, %-d %b %Y")

    # Anchor logs next to this script so cron runs don't scatter them around.
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    logfile_path = os.path.join(logs_dir, f"{today.strftime('%d%b%Y')}.log")
    setup_logging(logfile_path)

    config.validate(require_email=not args.dry_run)

    llm = Gemini()
    client = ArxivClient()
    stats = RunStats()
    entries = []

    try:
        ids = client.fetch_paper_ids(config.arxiv_section, date)
        logging.info("Found %d papers for %s", len(ids), date)
        papers = client.fetch_metadata(ids)
        if len(papers) < len(ids):
            logging.warning("Metadata missing for %d papers", len(ids) - len(papers))
        if args.limit:
            papers = papers[:args.limit]

        entries = process_papers(llm, client, papers, stats)
    except Exception as e:
        logging.exception("Run failed: %s", e)
        stats.aborted_reason = stats.aborted_reason or f"run failed: {e}"

    logging.info("Done: %d scanned, %d relevant, %d errors",
                 stats.scanned, stats.relevant, stats.errors)

    subject = f"arXiv papers for {date}"
    body = build_digest(date, entries, stats)

    if args.dry_run:
        digest_path = os.path.join(logs_dir, f"digest-{today.strftime('%d%b%Y')}.html")
        with open(digest_path, "w") as f:
            f.write(body)
        logging.info("Dry run: digest written to %s", digest_path)
    else:
        send_email(subject, body, entries, attachment_path=logfile_path)


if __name__ == "__main__":
    main()
