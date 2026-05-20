import requests
import json
import os
from datetime import datetime

def fetch_pandas_issues(limit=500, state="closed"):
    url = f"https://api.github.com/repos/pandas-dev/pandas/issues"
    params = {"state": state, "per_page": 100, "page": 1}
    issues = []
    while len(issues) < limit and params["page"] < 10:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        issues.extend(data)
        params["page"] += 1
    # Filter out PRs (pull_request key exists)
    issues = [i for i in issues if "pull_request" not in i]
    # Keep only needed fields
    filtered = []
    for i in issues[:limit]:
        filtered.append({
            "id": i["id"],
            "title": i["title"],
            "body": i["body"] or "",
            "labels": [l["name"] for l in i["labels"]],
            "created_at": i["created_at"],
            "state": i["state"]
        })
    return filtered

if __name__ == "__main__":
    issues = fetch_pandas_issues(limit=500)
    with open("data_pipeline/pandas_issues.json", "w") as f:
        json.dump(issues, f, indent=2)
    print(f"Saved {len(issues)} issues to pandas_issues.json")