#!/usr/bin/env python3
"""
Prompt-based automation: summarizes system monitoring logs and detects
issues using the Gemini API. Reads GEMINI_API_KEY from environment (.env
locally, or a GitHub Actions secret in CI). Never hardcode the key here.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv()  # loads .env when run locally; no-op in CI (key comes from secret)

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set. Check your .env file or CI secret.", file=sys.stderr)
    sys.exit(1)

LOG_FILE = "exp_1_scheduling/system_monitor.log"
REPORT_FILE = "exp_4_cicd/latest_report.md"
MAX_LOG_CHARS = 1500  # keep the prompt small and within free-tier limits


def read_recent_log(path, max_chars=MAX_LOG_CHARS):
    if not os.path.exists(path):
        return "No log file found at this path."
    with open(path, "r") as f:
        content = f.read()
    return content[-max_chars:]


def main():
    log_content = read_recent_log(LOG_FILE)

    client = genai.Client(api_key=API_KEY)

    prompt = (
        "You are a DevOps assistant. Read the following system monitoring log "
        "and produce a short report with exactly two sections:\n"
        "1. Summary - one paragraph describing overall system health.\n"
        "2. Issues Detected - a bullet list of any errors, warnings, or resource "
        "concerns (e.g. low disk space, high memory usage). If none, write "
        "'No issues detected.'\n\n"
        f"Log content:\n{log_content}"
    )

    # Try models in order of quota abundance; fall back gracefully.
    MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemma-4-31b-it"]
    report_text = None

    for model in MODELS:
        try:
            print(f"Trying {model}...", file=sys.stderr)
            interaction = client.interactions.create(model=model, input=prompt)
            report_text = interaction.output_text
            print(f"Success with {model}.", file=sys.stderr)
            break
        except Exception as e:
            print(f"  {model} unavailable: {str(e)[:160]}", file=sys.stderr)

    if report_text is None:
        report_text = (
            "### Summary\n\nAutomated AI analysis was unavailable for this run "
            "(all configured models exhausted their free-tier quota).\n\n"
            "### Issues Detected\n\n* Report generation skipped; see the raw "
            "monitoring log for current system state."
        )

    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        f.write("# Automated System Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(report_text)

    print(f"Report written to {REPORT_FILE}")
    print(report_text)


if __name__ == "__main__":
    main()