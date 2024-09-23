import argparse
import logging
import os
import re
import requests
import smtplib
import time
import cv2
import numpy as np

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from typing import List, Tuple

import fitz
from bs4 import BeautifulSoup

import config
from LLMs.gemini import Gemini
from LLMs.llm_interface import LLMInterface

def fetch_arxiv_page(section: str) -> str:
    """Fetch the webpage content."""
    arxiv_url = f"https://arxiv.org/list/{section}/recent?skip=0&show=1000"
    response = requests.get(arxiv_url)
    response.raise_for_status()
    return response.content

def parse_articles(web_content: str, date: str) -> List:
    """Find all today's articles."""
    soup = BeautifulSoup(web_content, 'html.parser')
    date_section = soup.find('h3', string=re.compile(re.escape(date)))
    if date_section:
        articles = date_section.find_next_siblings('dt')
        return articles
    return []

def download_pdf(pdf_url: str, pdf_filename: str) -> None:
    """Download pdf file from arxiv."""
    response = requests.get(pdf_url)
    response.raise_for_status()
    with open(pdf_filename, 'wb') as f:
        f.write(response.content)

def parse_pdf(pdf_filename: str) -> str:
    try:
        doc = fitz.open(pdf_filename)
        text = ""
        teaser_figure = None
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text += page.get_text()
            # Save teaser figure as the first figure in the paper
            if teaser_figure is None:
                images = page.get_images(full=True)
                if len(images) > 0:
                    teaser_figure = fitz.Pixmap(doc, images[0][0])
                    if teaser_figure.n < 5:  # this is a GRAY or RGB image
                        teaser_figure = np.frombuffer(teaser_figure.tobytes(), dtype=np.uint8)
                        teaser_figure = cv2.imdecode(teaser_figure, cv2.IMREAD_COLOR)  # Convert to CV2 image
                    else:  # CMYK: convert to RGB
                        teaser_figure = fitz.Pixmap(fitz.csRGB, teaser_figure)  # convert CMYK to RGB
                        teaser_figure = np.frombuffer(teaser_figure.tobytes(), dtype=np.uint8)
                        teaser_figure = cv2.imdecode(teaser_figure, cv2.IMREAD_COLOR)
                    k = 500 / teaser_figure.shape[1]
                    teaser_figure = cv2.resize(teaser_figure, (0,0), fx=k, fy=k)
        return text, teaser_figure
    except Exception as e:
        logging.info(f"PyMuPDF failed: {e}")
        return ""

def process_article(llm: LLMInterface, article) -> Tuple[str, str, bool, str]:
    """Process single article."""
    try:
        title_div = article.find_next('div', class_='list-title')
        pdf_link = article.find_next('a', href=re.compile(r'/pdf/'))
        if title_div and pdf_link:
            title = title_div.text.strip()
            pdf_url = "https://arxiv.org" + pdf_link['href']
            pdf_filename = pdf_url.split('/')[-1] + '.pdf'
            
            download_pdf(pdf_url, pdf_filename)
            text, teaser_figure = parse_pdf(pdf_filename)
            is_relevant, response_text = llm.analyze_text(text)
            
            os.remove(pdf_filename)
            
            return title, pdf_url, is_relevant, response_text, text, teaser_figure
    except Exception as e:
        logging.error(f"Error processing article: {e}")
        return None
    finally:
        if pdf_filename and os.path.exists(pdf_filename):
            os.remove(pdf_filename)

def send_email(email_subject: str, email_body: str, teaser_figures: List[str] = None, attachment_path: str=None) -> None:
    """Send the email."""
    msg = MIMEMultipart()
    msg['From'] = config.email_from
    msg['To'] = config.email_to
    msg['Subject'] = email_subject
    msg['Content-Type'] = 'text/html; charset=utf-8'
    msg.attach(MIMEText(email_body, 'html'))

    if teaser_figures is not None:
        for idx, teaser_figure in enumerate(teaser_figures):
            _, img_buffer = cv2.imencode('.png', teaser_figure)  # Encode as PNG
            img_data = img_buffer.tobytes()  # Convert to bytes
            img_mime = MIMEImage(img_data, _subtype='png')
            img_mime.add_header('Content-ID', f'<teaser_image_{idx}>')
            img_mime.add_header('Content-Disposition', 'inline', filename=f'teaser_figure_{idx}.png')
            msg.attach(img_mime)

    if attachment_path:
        try:
            with open(attachment_path, 'rb') as file:
                part = MIMEApplication(file.read(), Name="log.txt")
            part['Content-Disposition'] = f'attachment; filename="log.txt"'
            msg.attach(part)
        except Exception as e:
            logging.error(f"Failed to attach log file: {e}")

    try:
        server = smtplib.SMTP(config.email_smtp_server, config.email_smtp_port)
        server.starttls()
        server.login(config.email_username, config.email_password)
        text = msg.as_string()
        server.sendmail(config.email_from, config.email_to, text)
        server.quit()
        logging.info("Email sent successfully")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', help='Date for processing, if not today')
    args = parser.parse_args()
    
    today = datetime.now()
    if args.date is not None:
        specific_date = args.date
    else:
        # Find today's date 
        specific_date = today.strftime('%a, %-d %b %Y')

    # Initialize the LLM
    llm = Gemini()

    # Initialize logging 
    os.makedirs("logs", exist_ok=True)
    logfile_path = f"logs/{today.strftime('%d%b%Y')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logfile_path),
            logging.StreamHandler()
        ]
    )

    try:
        # Find all today's articles
        web_content = fetch_arxiv_page(config.arxiv_section)
        articles = parse_articles(web_content, specific_date)

        email_subject = f"Arxiv Papers for {specific_date}"
        email_body = f"<h2>Papers for {specific_date}:</h2>"

        if len(articles) > 0:
            teaser_figure_idx = 0
            teaser_figures = []
            # Iterate over articles to find the relevant ones
            for article_id, article in enumerate(articles):
                time.sleep(5)
                logging.info(f"{'*' * 100} Paper ID: {article_id}")
                try:
                    title, pdf_url, is_relevant, response_text, article_text, teaser_figure = process_article(llm, article)
                    if is_relevant:
                        email_body += f"<p><strong>{title}<br>"
                        email_body += f"<a href='{pdf_url}'>PDF Link</a></p><br>"
                        email_body += f"<p>{response_text}</p><br>"
                        if teaser_figure is not None:
                            email_body += f"<p><img src='cid:teaser_image_{teaser_figure_idx}' alt='Teaser Figure'></p><br>"
                            teaser_figures.append(teaser_figure)
                            teaser_figure_idx += 1
                        else:
                            email_body += "<p>No teaser image available.</p><br>"
                        logging.info(f"Yes: {title}")
                    else:
                        logging.info(f"No: {title}")
                        logging.info(response_text)
                except Exception as e:
                    logging.error(f"Failed to process the article: {e}")

                break

        else:
            logging.info(f"No articles found for {specific_date}")

        send_email(email_subject, email_body, teaser_figures=teaser_figures, attachment_path=logfile_path)
    
    except Exception as e:
        logging.error(f"Failed to process articles: {e}")


if __name__ == "__main__":
    main()
