"""Build and send the daily digest email."""

import base64
import html
import logging
import smtplib
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import config
from arxiv_client import Paper


@dataclass
class DigestEntry:
    paper: Paper
    summary_html: str
    matched_interest: str
    figure_png: Optional[bytes] = None


@dataclass
class RunStats:
    scanned: int = 0
    relevant: int = 0
    errors: int = 0
    aborted_reason: str = ""


def build_digest(date: str, entries: List[DigestEntry], stats: RunStats,
                 inline_images: bool = False) -> str:
    """Render the digest HTML.

    Figures are referenced as cid: attachments for emails; with
    `inline_images` they are embedded as base64 data URIs instead, so the
    HTML is viewable in a browser (used by --dry-run).
    """
    parts = [f"<h2>arXiv {html.escape(config.arxiv_section)} papers for {html.escape(date)}</h2>"]

    if not entries:
        parts.append("<p>No relevant papers today.</p>")

    for idx, entry in enumerate(entries):
        paper = entry.paper
        parts.append("<hr>")
        parts.append(
            f"<h3><a href='{paper.abs_url}'>{html.escape(paper.title)}</a></h3>"
            f"<p><i>{html.escape(', '.join(paper.authors))}</i><br>"
            f"Interest: <b>{html.escape(entry.matched_interest)}</b> &middot; "
            f"<a href='{paper.pdf_url}'>PDF</a></p>"
        )
        parts.append(f"<p>{entry.summary_html}</p>")
        if entry.figure_png is not None:
            if inline_images:
                src = f"data:image/png;base64,{base64.b64encode(entry.figure_png).decode()}"
            else:
                src = f"cid:teaser_image_{idx}"
            parts.append(f"<p><img src='{src}' alt='Teaser figure'></p>")

    parts.append("<hr>")
    footer = f"Scanned {stats.scanned} papers, {stats.relevant} relevant, {stats.errors} errors."
    if stats.aborted_reason:
        footer += f" <b>Run aborted early: {html.escape(stats.aborted_reason)}</b>"
    parts.append(f"<p><small>{footer}</small></p>")
    return "\n".join(parts)


def send_email(subject: str, body_html: str, entries: List[DigestEntry],
               attachment_path: Optional[str] = None) -> None:
    msg = MIMEMultipart()
    msg["From"] = config.email_from
    msg["To"] = config.email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    for idx, entry in enumerate(entries):
        if entry.figure_png is None:
            continue
        image = MIMEImage(entry.figure_png, _subtype="png")
        image.add_header("Content-ID", f"<teaser_image_{idx}>")
        image.add_header("Content-Disposition", "inline", filename=f"teaser_figure_{idx}.png")
        msg.attach(image)

    if attachment_path:
        try:
            with open(attachment_path, "rb") as f:
                attachment = MIMEApplication(f.read(), Name="log.txt")
            attachment["Content-Disposition"] = 'attachment; filename="log.txt"'
            msg.attach(attachment)
        except OSError as e:
            logging.error("Failed to attach log file: %s", e)

    with smtplib.SMTP(config.email_smtp_server, config.email_smtp_port, timeout=60) as server:
        server.starttls()
        server.login(config.email_username, config.email_password)
        server.sendmail(config.email_from, [config.email_to], msg.as_string())
    logging.info("Email sent to %s", config.email_to)
