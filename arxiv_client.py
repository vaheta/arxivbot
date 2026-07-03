"""Everything that talks to arxiv.org: listing pages, metadata API, PDFs."""

import io
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import fitz
import requests
from bs4 import BeautifulSoup
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

LISTING_URL = "https://arxiv.org/list/{section}/recent?skip=0&show=2000"
API_URL = "https://export.arxiv.org/api/query"
API_BATCH_SIZE = 100

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

TEASER_WIDTH = 500  # px, width of the figure embedded in the email
MIN_FIGURE_SIZE = (200, 100)  # skip logos, rules and other decorations
MAX_FIGURE_PAGES = 3  # only look for a teaser figure in the first pages


@dataclass
class Paper:
    arxiv_id: str
    title: str = ""
    abstract: str = ""
    authors: List[str] = field(default_factory=list)

    @property
    def abs_url(self) -> str:
        return f"https://arxiv.org/abs/{self.arxiv_id}"

    @property
    def pdf_url(self) -> str:
        return f"https://arxiv.org/pdf/{self.arxiv_id}"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


class ArxivClient:
    """HTTP client for arxiv.org with retries and a politeness delay."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "arxivbot (personal daily digest)"
        # Only retry connection-level failures here; HTTP 429/5xx need waits of
        # tens of seconds on arxiv.org and are handled in _get instead.
        retry = Retry(total=None, connect=3, read=2, status=0, backoff_factor=1)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self._last_request_time = 0.0

    def _get(self, url: str, attempts: int = 5, **kwargs) -> requests.Response:
        for attempt in range(1, attempts + 1):
            wait = config.arxiv_request_delay - (time.monotonic() - self._last_request_time)
            if wait > 0:
                time.sleep(wait)
            response = self.session.get(url, timeout=60, **kwargs)
            self._last_request_time = time.monotonic()
            if response.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                retry_after = response.headers.get("Retry-After", "")
                delay = int(retry_after) if retry_after.isdigit() else 10 * 2 ** (attempt - 1)
                logging.warning("HTTP %d from arxiv (attempt %d/%d), waiting %ds",
                                response.status_code, attempt, attempts, min(delay, 120))
                time.sleep(min(delay, 120))
                continue
            response.raise_for_status()
            return response

    def fetch_paper_ids(self, section: str, date: str) -> List[str]:
        """Return the arXiv ids announced on `date` (e.g. 'Fri, 3 Jul 2026')."""
        response = self._get(LISTING_URL.format(section=section))
        soup = BeautifulSoup(response.content, "html.parser")

        heading = None
        for h3 in soup.find_all("h3"):
            if h3.get_text().strip().startswith(date):
                heading = h3
                break
        if heading is None:
            available = [h3.get_text().strip() for h3 in soup.find_all("h3")]
            logging.warning("No listing found for '%s'. Available: %s", date, available)
            return []

        ids = []
        # dt entries are siblings of the h3 date headings inside one <dl>;
        # collect only until the next heading so we stay within one day.
        for sibling in heading.find_next_siblings(["h3", "dt"]):
            if sibling.name == "h3":
                break
            link = sibling.find("a", href=re.compile(r"/abs/"))
            if link:
                ids.append(link["href"].split("/abs/")[-1].strip())
        return ids

    def fetch_metadata(self, arxiv_ids: List[str]) -> List[Paper]:
        """Fetch title, abstract and authors for the given ids in batches."""
        papers = []
        for start in range(0, len(arxiv_ids), API_BATCH_SIZE):
            batch = arxiv_ids[start:start + API_BATCH_SIZE]
            papers.extend(self._fetch_metadata_batch(batch))
        # The API does not preserve the requested order; restore listing order.
        order = {arxiv_id: idx for idx, arxiv_id in enumerate(arxiv_ids)}
        papers.sort(key=lambda p: order.get(p.arxiv_id, len(order)))
        return papers

    def _fetch_metadata_batch(self, batch: List[str], attempts: int = 3) -> List[Paper]:
        params = {"id_list": ",".join(batch), "max_results": len(batch)}
        for attempt in range(1, attempts + 1):
            response = self._get(API_URL, params=params)
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError:
                # The API replies with plain text (e.g. "Rate exceeded.") when
                # throttling; back off and retry.
                logging.warning(
                    "arXiv API returned non-XML (attempt %d/%d): %.80s",
                    attempt, attempts, response.text,
                )
                time.sleep(10 * attempt)
                continue

            papers = []
            for entry in root.findall("atom:entry", ATOM_NS):
                entry_id = entry.findtext("atom:id", "", ATOM_NS)
                arxiv_id = entry_id.rsplit("/abs/", 1)[-1]
                arxiv_id = re.sub(r"v\d+$", "", arxiv_id)  # strip version suffix
                if not arxiv_id:
                    continue
                papers.append(Paper(
                    arxiv_id=arxiv_id,
                    title=_normalize_whitespace(entry.findtext("atom:title", "", ATOM_NS)),
                    abstract=_normalize_whitespace(entry.findtext("atom:summary", "", ATOM_NS)),
                    authors=[
                        _normalize_whitespace(author.findtext("atom:name", "", ATOM_NS))
                        for author in entry.findall("atom:author", ATOM_NS)
                    ],
                ))
            return papers
        raise RuntimeError(f"arXiv API kept failing for batch starting with {batch[0]}")

    def fetch_pdf(self, paper: Paper) -> bytes:
        return self._get(paper.pdf_url).content


def extract_text_and_figure(pdf_bytes: bytes) -> Tuple[str, Optional[bytes]]:
    """Extract the paper text (capped) and a teaser figure as PNG bytes."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        chunks = []
        total = 0
        for page in doc:
            text = page.get_text()
            chunks.append(text)
            total += len(text)
            if total >= config.max_pdf_chars:
                break
        text = "".join(chunks)[:config.max_pdf_chars]
        figure = _extract_teaser_figure(doc)
    return text, figure


def _extract_teaser_figure(doc: "fitz.Document") -> Optional[bytes]:
    """Return the first reasonably sized figure as PNG bytes, or None."""
    for page_num in range(min(MAX_FIGURE_PAGES, doc.page_count)):
        for image_info in doc.load_page(page_num).get_images(full=True):
            try:
                extracted = doc.extract_image(image_info[0])
                image = Image.open(io.BytesIO(extracted["image"]))
                if image.width < MIN_FIGURE_SIZE[0] or image.height < MIN_FIGURE_SIZE[1]:
                    continue
                image = image.convert("RGB")
                scale = TEASER_WIDTH / image.width
                image = image.resize((TEASER_WIDTH, max(1, round(image.height * scale))))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue()
            except Exception as e:
                logging.debug("Skipping unreadable image on page %d: %s", page_num, e)
    return None
