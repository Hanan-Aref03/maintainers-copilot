import requests
import json
import os

def fetch_resolved_issues(limit=200):
    url = "https://api.github.com/repos/pandas-dev/pandas/issues"
    params = {"state": "closed", "per_page": 100, "page": 1}
    issues = []
    while len(issues) < limit and params["page"] < 5:
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        # exclude pull requests
        issues.extend([i for i in data if "pull_request" not in i])
        params["page"] += 1
    # keep only relevant fields and truncate body
    kb = []
    for i in issues[:limit]:
        kb.append({
            "id": i["id"],
            "title": i["title"],
            "body": (i["body"] or "")[:2000],
            "url": i["html_url"],
            "type": "issue"
        })
    return kb

if __name__ == "__main__":
    kb = fetch_resolved_issues(200)
    os.makedirs("data_pipeline", exist_ok=True)
    with open("data_pipeline/knowledge_base.json", "w") as f:
        json.dump(kb, f, indent=2)
    print(f"Saved {len(kb)} resolved issues to knowledge_base.json")