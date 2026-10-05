#!/usr/bin/env python3

import os
import sys
import requests

def get_failed_jobs_summary(max_log_lines: int = 40) -> str:
    api_url = os.environ["CI_API_V4_URL"]
    project_id = os.environ["CI_PROJECT_ID"]
    pipeline_id = os.environ["CI_PIPELINE_ID"]
    token = os.environ["GIT_API_TOKEN"]  # PAT or project access token, api scope

    headers = {"PRIVATE-TOKEN": token}

    jobs_url = f"{api_url}/projects/{project_id}/pipelines/{pipeline_id}/jobs"
    resp = requests.get(jobs_url, headers=headers, params={"per_page": 100})
    resp.raise_for_status()
    jobs = resp.json()

    failed_jobs = [j for j in jobs if j["status"] == "failed"]

    if not failed_jobs:
        return "No failed jobs found (pipeline may have failed for another reason)."

    sections = []
    for job in failed_jobs:
        job_id = job["id"]
        name = job["name"]
        stage = job["stage"]

        trace_url = f"{api_url}/projects/{project_id}/jobs/{job_id}/trace"
        trace_resp = requests.get(trace_url, headers=headers)
        trace_resp.raise_for_status()
        log_lines = trace_resp.text.strip().splitlines()
        tail = "\n".join(log_lines[-max_log_lines:])

        sections.append(
            f"**Job:** `{name}` (stage: `{stage}`)\n"
            f"```\n{tail}\n```"
        )

    return "\n\n".join(sections)

if __name__ == "__main__":
    print(get_failed_jobs_summary())