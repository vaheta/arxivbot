# ArxivBot

<img src="images/arxibot.webp" alt="ArxivBot" width="400">

ArxivBot is a Python script that automates the process of staying up-to-date with the latest research in your field. It fetches papers from [arxiv.org](https://arxiv.org), filters them based on your interests, summarizes them using a language model, and sends you a daily email with the results.

## How it works

1. Fetches the day's announcement — ids, titles and abstracts — from the arXiv Atom feed ([rss.arxiv.org](https://rss.arxiv.org)) in a single request. For `--date` runs, or if the feed is unavailable, it falls back to scraping the listing page and querying the export API (which rate-limits aggressively per IP).
2. **Classifies every paper from its title + abstract only** using a lightweight Gemini model (`gemini-3.5-flash-lite`), guided by your research interests and example papers.
3. Only for the papers judged relevant, downloads the PDF, extracts the text and a teaser figure, and generates a summary with a stronger model (`gemini-3.6-flash`).
4. Sends a single HTML digest email with summaries, figures, links, and the run log attached.

This two-stage design keeps the bot fast and inside the Gemini API **free tier**: the high-volume classification goes to the model with the largest free daily quota, while the expensive full-text summarization only runs for the handful of relevant papers.

## Features

- Fetches the latest research papers from arxiv.org.
- Filters papers with an LLM classifier tuned by your interests and few-shot examples.
- Auto-includes papers by authors you follow, bypassing the classifier.
- Downloads and summarizes only the relevant papers (full PDF text).
- Extracts a teaser figure from each relevant paper.
- Sends an email digest with summaries, figures and the attached log.
- Rate-limited and retrying HTTP/LLM clients that respect arXiv and Gemini quotas.
- Easy to configure and automate with cron.

## Prerequisites

- Conda (Miniconda or Anaconda)

## Installation

1. **Clone the repository:**

   ```sh
   git clone https://github.com/yourusername/arxivbot.git
   cd arxivbot
   ```

2. **Create and activate the Conda environment:**

   ```sh
    conda env create -f environment.yml
    conda activate arxivbot
   ```
3. **Create a Mailgun account or set up an email server:**

    Mailgun has a free plan for a small number of emails sent per month, but you can also use your own email server for this.

    1. Create a Mailgun Account:
        - Go to the Mailgun website and sign up for an account.
        - Follow the instructions to verify your email address and set up your domain.
    2. Get Your API Key:
        - Once your account is set up, log in to the Mailgun dashboard.
        - Navigate to the "API" section.
        - Copy the "Private API Key" and use it as the EMAIL_PASSWORD in your .env file.
        - Use your Mailgun domain and email as the EMAIL_FROM.

4. **Generate a Gemini API key:**

    The free tier of the Gemini API is enough for daily use with the default models. Check the live quotas for your project at [aistudio.google.com/rate-limit](https://aistudio.google.com/rate-limit).
    - Go to [Google AI Studio](https://aistudio.google.com) and sign up for an account if you don't already have one.
    - Press "Get API Key".
    - Create a new API key.
    - Copy the API key and use it as the GENAI_API_TOKEN in your .env file.

5. **Set up environment variables:**
    Add the token and email server info to .env_template file and rename it to .env.
    ```sh
    EMAIL_FROM=<your Mailgun or email server email>
    EMAIL_TO=recipient@example.com
    EMAIL_SMTP_SERVER=<smtp.mailgun.com or email server smtp>
    EMAIL_SMTP_PORT=587
    EMAIL_USERNAME=<your Mailgun or email server email>
    EMAIL_PASSWORD=<your Mailgun or email server password>
    GENAI_API_TOKEN=<your Gemini API token>
    ```

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
python main.py --date 'Thu, 2 Jul 2026'  # process a specific listing day
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

The dependencies are listed in the environment.yml file and include:

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
