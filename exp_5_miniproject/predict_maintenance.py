#!/usr/bin/env python3
"""
Predictive maintenance: analyses system metrics for resource-exhaustion risk.

Free-tier aware:
  - Tries models in ascending order of quota scarcity (abundant models first).
  - Downsamples and compacts the metrics to minimise tokens per request.
  - Falls back to a local rule-based verdict if every model is unavailable,
    so the pipeline still produces a result instead of failing.
"""

import json
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv()

CSV_FILE = "exp_5_miniproject/metrics.csv"
REPORT_FILE = "exp_5_miniproject/prediction_report.md"
VERDICT_FILE = "exp_5_miniproject/verdict.json"

# Ordered by daily quota: spend abundant models first, save scarce ones.
MODEL_CHAIN = [
    ("gemini-3.1-flash-lite", 500),
    ("gemini-3.5-flash-lite", 500),
    ("gemma-4-31b-it",     14400),
    ("gemini-3.6-flash",      20),
]

SAMPLE_POINTS = 8       # readings sent to the model (keeps tokens ~400)
RETRY_DELAY = 4         # seconds between models
DISK_LIMIT = 80
MEM_LIMIT = 90


def read_metrics(path):
    """Parse the CSV into a list of dicts. Exits if unusable."""
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run collect_metrics.sh first.", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        lines = [ln for ln in f.read().strip().split("\n") if ln.strip()]

    if len(lines) < 2:
        print("ERROR: Not enough data rows for trend analysis.", file=sys.stderr)
        sys.exit(1)

    rows = []
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) < 5:
            continue
        try:
            rows.append({
                "timestamp": parts[0],
                "disk": float(parts[1]),
                "mem": float(parts[2]),
                "load": float(parts[3]),
                "procs": int(parts[4]),
            })
        except ValueError:
            continue

    if not rows:
        print("ERROR: No valid data rows found.", file=sys.stderr)
        sys.exit(1)

    return rows


def downsample(rows, n=SAMPLE_POINTS):
    """Evenly sample n readings across the full window, always keeping the ends.

    Sending 200 raw rows wastes tokens; the trend is preserved by sampling.
    """
    if len(rows) <= n:
        return rows
    step = (len(rows) - 1) / (n - 1)
    return [rows[round(i * step)] for i in range(n)]


def compact(rows):
    """Render readings as a minimal token-efficient block."""
    lines = ["time|disk%|mem%|load|procs"]
    for r in rows:
        t = r["timestamp"].split("T")[-1][:5]  # HH:MM only
        lines.append(f"{t}|{r['disk']}|{r['mem']}|{r['load']}|{r['procs']}")
    return "\n".join(lines)


def build_prompt(rows_all, rows_sample):
    first, last = rows_all[0], rows_all[-1]
    span = f"{len(rows_all)} readings, {first['timestamp']} to {last['timestamp']}"
    trend = (
        f"disk {first['disk']}->{last['disk']}%, "
        f"mem {first['mem']}->{last['mem']}%"
    )
    return (
        "Linux server predictive maintenance. Assess resource-exhaustion risk.\n"
        "Reply with JSON only, no fences, no preamble:\n"
        '{"risk_level":"low|medium|high","summary":"1 short paragraph",'
        '"predictions":["<=3 short items"],"recommended_actions":["<=3 short items"]}\n'
        f"Use high only if exhaustion is imminent. Thresholds: disk {DISK_LIMIT}%, mem {MEM_LIMIT}%.\n"
        f"Window: {span}. Overall: {trend}.\n"
        f"Samples:\n{compact(rows_sample)}"
    )


def parse_verdict(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    # Some models wrap JSON in stray text; extract the outermost object.
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            raise json.JSONDecodeError("No JSON object found", raw, 0)
        raw = raw[start:end + 1]

    verdict = json.loads(raw)
    if verdict.get("risk_level") not in ("low", "medium", "high"):
        verdict["risk_level"] = "medium"
    return verdict


def try_models(api_key, prompt):
    """Walk the model chain until one succeeds. Returns verdict or None."""
    client = genai.Client(api_key=api_key)

    for model, quota in MODEL_CHAIN:
        try:
            print(f"Trying {model} (daily quota {quota})...", file=sys.stderr)
            interaction = client.interactions.create(model=model, input=prompt)
            verdict = parse_verdict(interaction.output_text)
            verdict["source"] = model
            print(f"Success with {model}.", file=sys.stderr)
            return verdict

        except json.JSONDecodeError:
            print(f"  {model}: response was not valid JSON.", file=sys.stderr)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                print(f"  {model}: quota exhausted, moving on.", file=sys.stderr)
            else:
                print(f"  {model}: {msg[:160]}", file=sys.stderr)

        time.sleep(RETRY_DELAY)

    return None


def local_verdict(rows, reason):
    """Rule-based fallback. No API required."""
    latest, first = rows[-1], rows[0]
    delta = latest["disk"] - first["disk"]

    if latest["disk"] >= 95 or latest["mem"] >= MEM_LIMIT:
        risk = "high"
    elif latest["disk"] >= DISK_LIMIT or delta >= 5:
        risk = "medium"
    else:
        risk = "low"

    return {
        "risk_level": risk,
        "summary": (
            f"Rule-based assessment over {len(rows)} readings: disk at "
            f"{latest['disk']}% ({delta:+.1f} points across the window), memory "
            f"{latest['mem']}%, load {latest['load']}. AI analysis unavailable: {reason}"
        ),
        "predictions": [
            f"Disk at {latest['disk']}% against a {DISK_LIMIT}% threshold."
        ],
        "recommended_actions": [
            "Review consumers with: du -xh / | sort -rh | head -n 20",
            "Re-run analysis once model quota resets.",
        ],
        "source": "local-fallback",
    }


def write_outputs(verdict):
    os.makedirs(os.path.dirname(VERDICT_FILE), exist_ok=True)

    with open(VERDICT_FILE, "w") as f:
        json.dump(verdict, f, indent=2)

    with open(REPORT_FILE, "w") as f:
        f.write("# Predictive Maintenance Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"**Risk level:** {verdict.get('risk_level', 'unknown').upper()}\n\n")
        f.write(f"**Analysis source:** {verdict.get('source', 'unknown')}\n\n")
        f.write("## Summary\n\n")
        f.write(verdict.get("summary", "N/A") + "\n\n")
        f.write("## Predictions\n\n")
        for item in verdict.get("predictions") or ["None."]:
            f.write(f"- {item}\n")
        f.write("\n## Recommended Actions\n\n")
        for item in verdict.get("recommended_actions") or ["None."]:
            f.write(f"- {item}\n")


def main():
    rows = read_metrics(CSV_FILE)
    sample = downsample(rows)
    prompt = build_prompt(rows, sample)

    print(f"Loaded {len(rows)} readings, sending {len(sample)} samples "
          f"(~{len(prompt) // 4} tokens).")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        verdict = local_verdict(rows, "GEMINI_API_KEY not configured")
    else:
        verdict = try_models(api_key, prompt) or \
                  local_verdict(rows, "all models exhausted or unavailable")

    write_outputs(verdict)

    print(f"Risk level: {verdict['risk_level']} (source: {verdict['source']})")
    print(f"Report written to {REPORT_FILE}")
    sys.exit(0)  # A risk finding is a result, not a build failure.


if __name__ == "__main__":
    main()