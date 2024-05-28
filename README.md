# ArxivBot

<img src="images/arxibot.webp" alt="ArxivBot" width="400">

ArxivBot is a Python script that automates the process of staying up-to-date with the latest research in your field. It fetches papers from [arxiv.org](https://arxiv.org), filters them based on your interests, summarizes them using a language model, and sends you a daily email with the results. 

## Features

- Fetches the latest research papers from arxiv.org.
- Filters papers based on predefined research interests.
- Uses a language model to generate summaries of relevant papers.
- Sends an email with the summaries and attached logs.
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

4. **Generate a token for Gemini Flash 1.5:**
    
    Gemini Flash is recommended for its large context window and free tier, but you can use other language models. You'll need to add them to LLMs directory with a proper interface.
        - Go to the [Google AI Studio](aistudio.google.com) and sign up for an account if you don't already have one.
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
The configuration is managed in the config.py file. The default settings are for the Computer Vision section, but you can set your own section by updating the arxiv_section variable in config.py.

- arxiv_section: Section URL for fetching papers from arxiv.org (default is for Computer Vision and Pattern Recognition - cs.CV). 
- interests: List of research interests to filter the papers. 

## Usage

To run the script, simply execute:

```sh
chmod +x runme.sh
./runme.sh
```

The script will fetch the latest papers, filter them, generate summaries, and send an email with the results.

## Log File
The script generates a log file in the logs directory. This log file is also attached to the email sent by the script.

## Automating with Cron

You can automate the execution of the script using cron jobs.

### Setting up Cron on Linux and Mac

1. Open your crontab file:

    ```sh
    crontab -e
    ```
2. Add a new cron job to run runme.sh at your desired frequency. Here’s how you can set up your cron job to run every day at 9 AM, Monday through Friday:
    ```sh
    0 9 * * 1-5 /path/to/your/arxivbot/runme.sh
    ```
    Make sure to replace /path/to/your/arxivbot/ with the actual path to your script.

### Setting up Task Scheduler on Windows
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

- python=3.9
- requests
- beautifulsoup4
- google-generativeai
- python-dotenv
- PyMuPDF

## Contributing
Feel free to open issues or submit pull requests for improvements or bug fixes.

## License
This project is licensed under the MIT License.
