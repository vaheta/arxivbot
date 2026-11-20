# ArxivBot

<img src="images/arxibot.webp" alt="ArxivBot" width="400">

ArxivBot is a Python script that automates the process of staying up-to-date with the latest research in your field. It fetches papers from [arxiv.org](https://arxiv.org), filters them based on your interests, summarizes them using a language model, and sends you a daily email with the results.

## How it works

1. Fetches the day's announcement — ids, titles and abstracts — from the arXiv Atom feed ([rss.arxiv.org](https://rss.arxiv.org)) in a single request. For `--date` runs, or if the feed is unavailable, it falls back to scraping the listing page and querying the export API (which rate-limits aggressively per IP).
2. **Classifies every paper from its title + abstract only** in groups of up to 12 using `gemini-3.5-flash-lite`, guided by your research interests and example papers.
3. For relevant papers and followed authors, downloads the PDF, extracts the text and a teaser figure, and generates a summary with a stronger model (`gemini-4-hydrogen`).
4. Sends a single HTML digest email with summaries, figures, links, and the run log attached.

Both default models have free input and output on the Gemini Developer API free tier. Use a free-tier project to keep inference free. Google sets limits per project and model. Batching reduces classification requests, and only papers selected for the digest use the summarizer. [Gemini pricing](https://aistudio.google.com/docs/pricing) · [Your project quotas](https://aistudio.google.com/rate-limit)

## Features

- Fetches the latest research papers from arxiv.org.
- Filters papers with an LLM classifier tuned by your interests and few-shot examples.
- Auto-includes papers by authors you follow, bypassing the classifier.
- Downloads and summarizes only the relevant papers (full PDF text).
- Extracts a teaser figure from each relevant paper.
- Sends an email digest with summaries, figures and the attached log.
- Rate-limited and retrying HTTP/LLM clients that respect arXiv and Gemini quotas.
- Runs on GitHub Actions or locally with cron.

## Run on GitHub Actions

The **Daily arXiv digest** workflow runs on GitHub's hosted Linux runner at **8:17 a.m. America/New_York, Monday through Friday**. The runner shuts down after each digest. Standard GitHub-hosted runners are free for this public repository. [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

1. In **Settings → Secrets and variables → Actions**, add the following *repository secrets*. A preview needs only the Gemini key. [Repository secrets](https://github.com/vaheta/arxivbot/settings/secrets/actions)

   | Secret | Value |
   | --- | --- |
   | `GENAI_API_TOKEN` | Gemini Developer API key from [Google AI Studio](https://aistudio.google.com/api-keys) |
   | `EMAIL_FROM` | Sender address authorized by your SMTP provider |
   | `EMAIL_TO` | Recipient address |
   | `EMAIL_SMTP_SERVER` | SMTP hostname |
   | `EMAIL_USERNAME` | SMTP login |
   | `EMAIL_PASSWORD` | SMTP password or app password. For Mailgun, use the domain's SMTP credentials. |

2. Port 587 uses STARTTLS. For a provider using implicit TLS, set the repository **variable** `EMAIL_SMTP_PORT` to `465`. Optional variables `CLASSIFIER_MODEL` and `SUMMARIZER_MODEL` override the defaults.
3. Under **Actions → Daily arXiv digest → Run workflow**, leave **Save an HTML preview** selected and set **limit** to `12` for a small trial. Download the `arxiv-digest` artifact from the run. Preview artifacts expire after seven days and are accessible to readers of the repository. For a weekend preview, enter a recent weekday listing date. [Daily digest workflow](https://github.com/vaheta/arxivbot/actions/workflows/digest.yml)
4. Scheduled runs email the whole digest. A manual run with preview unchecked also sends it, so repeating a delivery can send a second copy. Pushes to `main` only run the tests and report whether deployment settings are present.

If a run cannot scan any papers because of an error, it fails before sending an empty email. If part of a run succeeds, the subject is marked **[Incomplete]** and Actions shows a failure. Open the run log to see which stage failed. If you already run the bot via cron, turn off that schedule when switching to Actions to avoid duplicate email.

GitHub can delay scheduled jobs and disables the schedule after 60 days without repository activity in a public repo. Re-enable it on the workflow's Actions page. [GitHub scheduling behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## Run locally

Clone the repository and create a Python 3.11 environment:

```sh
git clone https://github.com/vaheta/arxivbot.git
cd arxivbot
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env_template .env
```

On Windows, activate the environment with `.venv\Scripts\activate`. For Conda, use `conda env create -f environment.yml` and `conda activate arxivbot` in place of the virtual environment and pip steps. Fill in the same settings from the table above in your local `.env` file.

## Configuration

The configuration is managed in `config.py`:

- `arxiv_section`: arXiv section to follow (default `cs.CV`).
- `followed_authors`: papers with any of these authors are added to the digest automatically, skipping the classifier. Names must match how they appear on arXiv (case-insensitive).
- `interests`: your research interests, each with a `topic` and a `description` that tells the classifier what does and does not belong to it. Be concrete — the classifier only sees titles and abstracts.
- `relevant_examples` / `irrelevant_examples`: titles of papers you do / don't want to receive. These few-shot examples anchor the classifier; updating them is the most effective way to tune precision.
- `classifier_model` / `summarizer_model` and their rate limits.
- `max_pdf_chars`: cap on the PDF text sent to the summarizer.

The prompt templates themselves live in `prompts.py`.

## Usage

To run the script, simply execute:

```sh
python main.py
```

Useful flags for testing and tuning:

```sh
python main.py --dry-run              # don't send email; write the digest HTML into logs/ (viewable in a browser, figures included)
python main.py --limit 10             # only process the first 10 papers
python main.py --date 'Thu, 2 Jul 2026'  # choose a day still on the recent listing
```

The classifier's per-paper decisions and reasoning are written to the log, which makes it easy to spot misclassifications and refine your interests/examples.

## Project layout

- `main.py` — CLI and orchestration.
- `config.py` — everything you may want to edit: section, interests, examples, models, email.
- `prompts.py` — prompt templates for the classifier and summarizer.
- `arxiv_client.py` — listing scraping, metadata API, PDF text/figure extraction.
- `emailer.py` — digest building and SMTP sending.
- `LLMs/` — LLM interface and the Gemini implementation (google-genai SDK). Other providers can be added by implementing `LLMInterface`.

## Log File

The script generates a log file in the logs directory. This log file is also attached to the email sent by the script.

## Automating with Cron

You can automate the execution of the script using cron jobs.

### Setting up Cron on Linux and Mac

1. Create a runme.sh script, add there the following content

    ```sh
    #!/bin/bash
    source /path/to/your/anaconda/bin/activate arxivbot
    python /path/to/your/arxivbot/main.py
    ```
    Make sure to replace /path/to/your/arxivbot and /path/to/your/anaconda with correct paths. Then run
    ```sh
    chmod +x runme.sh
    ```

2. Open your crontab file:

    ```sh
    crontab -e
    ```
3. Add a new cron job to run runme.sh at your desired frequency. Here’s how you can set up your cron job to run every day at 9 AM, Monday through Friday:
    ```sh
    0 9 * * 1-5 /path/to/your/arxivbot/runme.sh
    ```
    Make sure to replace /path/to/your/arxivbot/ with the actual path to your script.

### Setting up Task Scheduler on Windows
This was not tested!
1. Open Task Scheduler and create a new basic task.

2. Follow the wizard to set the trigger (e.g., daily at a specific time). In the advanced settings, select "Repeat task every" and specify the desired interval (e.g., every day). Under "Days," check "On these days" and select "Weekdays."

3. For the action, choose "Start a Program" and browse to your runme.bat file (you'll need to create a batch file to activate the Conda environment and run the script).
Example runme.bat file content:
    ```bat
    @echo off
    cd C:\path\to\your\arxivbot
    call conda activate arxivbot
    python main.py
    ```

## Dependencies

The hosted job installs from `requirements.txt`. The Conda environment is defined in `environment.yml`. Dependencies include:

- python=3.11
- requests
- beautifulsoup4
- python-dotenv
- PyMuPDF
- pillow
- google-genai

## Contributing
Feel free to open issues or submit pull requests for improvements or bug fixes.

## License
This project is licensed under the MIT License.
