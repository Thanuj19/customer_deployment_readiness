#!/usr/bin/env python3
"""Portfolio demo for tracking simulated customer-site deployment milestones."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MILESTONES = ["network_setup", "hardware_install", "data_validation", "user_training", "sat_signoff"]
ALLOWED = {"complete", "pending", "blocked", "not_started"}


def read_sites(path: Path) -> tuple[list[dict], list[str]]:
    rows = []
    issues = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"site", "customer", *MILESTONES}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
        for line_num, row in enumerate(reader, start=2):
            if not (row.get("site") or "").strip() or not (row.get("customer") or "").strip():
                issues.append(f"Row {line_num}: missing site or customer name; row excluded.")
                continue
            statuses = {}
            valid = True
            for milestone in MILESTONES:
                status = (row.get(milestone) or "").strip().lower()
                if status not in ALLOWED:
                    issues.append(f"Row {line_num}: invalid or missing status for {milestone}; row excluded.")
                    valid = False
                    break
                statuses[milestone] = status
            if valid:
                rows.append({"site": row["site"].strip(), "customer": row["customer"].strip(), **statuses})
    return rows, issues


def assess(rows: list[dict]) -> list[dict]:
    results = []
    for row in rows:
        complete = sum(row[name] == "complete" for name in MILESTONES)
        blockers = [f"{name.replace('_', ' ')}: {row[name]}" for name in MILESTONES if row[name] != "complete"]
        results.append({
            "site": row["site"],
            "customer": row["customer"],
            "readiness_pct": round(complete / len(MILESTONES) * 100),
            "completed_milestones": complete,
            "total_milestones": len(MILESTONES),
            "blockers": "; ".join(blockers) if blockers else "None",
            **{name: row[name] for name in MILESTONES},
        })
    return results


def local_summary(results: list[dict], issues: list[str]) -> str:
    ready = sum(row["readiness_pct"] == 100 for row in results)
    blocked = sum("blocked" in row["blockers"] for row in results)
    return (
        f"Reviewed {len(results)} simulated site(s): {ready} have all listed milestones complete, "
        f"{blocked} have at least one blocked milestone, and {len(issues)} input issue(s) were found. "
        "Confirm status and acceptance criteria with the customer team."
    )


def ai_summary(results: list[dict], issues: list[str]) -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return local_summary(results, issues), "local fallback"
    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    payload = {
        "model": model,
        "input": (
            "Summarize this simulated customer technology deployment tracker for an internal "
            "pilot review. Identify completion patterns and pending/blocked milestones. Do not "
            "invent causes, promise dates, or claim customer signoff. Clearly state the data is simulated.\n\n"
            + json.dumps({"sites": results, "input_issues": issues})
        ),
        "max_output_tokens": 180,
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"AI summary request failed: {exc}") from exc
    summary = body.get("output_text", "").strip()
    if not summary:
        summary = "\n".join(
            content.get("text", "")
            for item in body.get("output", [])
            for content in item.get("content", [])
            if content.get("type") == "output_text"
        ).strip()
    if not summary:
        raise RuntimeError("The AI API returned no summary text.")
    return summary, f"OpenAI Responses API ({model})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Score simulated deployment readiness and report open milestones.")
    parser.add_argument("--input", type=Path, default=Path("sample_deployments.csv"))
    parser.add_argument("--outdir", type=Path, default=Path("output"))
    args = parser.parse_args()
    try:
        sites, issues = read_sites(args.input)
        if not sites:
            raise ValueError("No valid deployment rows were found.")
        results = assess(sites)
        summary, source = ai_summary(results, issues)
        args.outdir.mkdir(parents=True, exist_ok=True)
        with (args.outdir / "site_readiness.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)
        issue_lines = [f"- {issue}" for issue in issues] if issues else ["- No missing or invalid fields were detected."]
        report = [
            "# Customer Deployment Readiness Review", "",
            "> SIMULATED DATA: sample milestones only; not evidence of a real customer deployment.", "",
            f"**Summary source:** {source}", "", "## Summary", summary, "", "## Input checks",
            *issue_lines,
            "", "See `site_readiness.csv` for readiness scores and open milestones.",
        ]
        (args.outdir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        print(summary)
        print(f"Readiness report written to {args.outdir.resolve()}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
