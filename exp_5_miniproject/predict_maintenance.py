#!/usr/bin/env python3
"""
Predictive maintenance: analyses the metrics CSV for trends and asks Gemini to
forecast resource exhaustion risk. Outputs both a human-readable Markdown report
and a machine-readable JSON verdict the CI pipeline can act on.
"""

import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set.", file=sys.stderr)
    sys.exit(1)

CSV_FILE = "exp_5_miniproject/metrics.csv"
REPORT_FILE = "exp_5_miniproject/prediction_report.md"
VERDICT_FILE = "exp_5_miniproject/verdict.json"
MAX_ROWS = 50  # keep the prompt small for the free tier


def read_metrics(path, max_rows=MAX_ROWS):
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run collect_metrics.sh first.", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        lines = f.read().strip().split("\n")
    if len(lines) < 2:
        print("ERROR: Not enough data rows for trend analysis.", file=sys.stderr)
        sys.exit(1)
    header = lines[0]
    rows = lines[1:][-max_rows:]
    return header + "\n" + "\n".join(rows), len(rows)


def main():
    csv_data, row_count = read_metrics(CSV_FILE)
    client = genai.Client(api_key=API_KEY)

    prompt = (
        "You are a predictive maintenance assistant for a Linux server. "
        "Analyse the CSV time-series metrics below and assess the risk of "
        "resource exhaustion.\n\n"
        "Respond ONLY with valid JSON (no markdown fences, no preamble) "
        "matching this schema:\n"
        "{\n"
        '  "risk_level": "low" | "medium" | "high",\n'
        '  "summary": "one paragraph on the observed trend",\n'
        '  "predictions": ["short forecast statements"],\n'
        '  "recommended_actions": ["concrete remediation steps"]\n'
        "}\n\n"
        "Set risk_level to high only if a resource is trending toward "
        "exhaustion in the near term.\n\n"
        f"Metrics ({row_count} readings):\n{csv_data}"
    )

    try:
        interaction = client.interactions.create(
            model="gemini-3.7-flash",
            input=prompt,
        )
    except Exception as e:
        print(f"ERROR: Gemini API call failed: {e}", file=sys.stderr)
        sys.exit(1)

    raw = interaction.output_text.strip()
    # Strip code fences if the model adds them despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        print("WARNING: Could not parse JSON. Falling back to low risk.", file=sys.stderr)
        verdict = {
            "risk_level": "low",
            "summary": raw[:500],
            "predictions": [],
            "recommended_actions": [],
        }

    os.makedirs(os.path.dirname(VERDICT_FILE), exist_ok=True)
    with open(VERDICT_FILE, "w") as f:
        json.dump(verdict, f, indent=2)

    # Build the human-readable report
    with open(REPORT_FILE, "w") as f:
        f.write("# Predictive Maintenance Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"**Risk level:** {verdict.get('risk_level', 'unknown').upper()}\n\n")
        f.write("## Summary\n\n")
        f.write(verdict.get("summary", "N/A") + "\n\n")
        f.write("## Predictions\n\n")
        for item in verdict.get("predictions", []) or ["None."]:
            f.write(f"- {item}\n")
        f.write("\n## Recommended Actions\n\n")
        for item in verdict.get("recommended_actions", []) or ["None."]:
            f.write(f"- {item}\n")

    print(f"Risk level: {verdict.get('risk_level')}")
    print(f"Report written to {REPORT_FILE}")


if __name__ == "__main__":
    main()