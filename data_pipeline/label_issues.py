import json
import random

def map_labels_to_type(labels):
    label_lower = [l.lower() for l in labels]
    if any(l in label_lower for l in ["bug", "regression"]):
        return "bug"
    if any(l in label_lower for l in ["enhancement", "feature", "new feature"]):
        return "feature"
    if any(l in label_lower for l in ["docs", "documentation"]):
        return "docs"
    if any(l in label_lower for l in ["question", "how-to"]):
        return "question"
    return "other"

def create_golden_set(input_file, output_file, sample_size=25):
    with open(input_file) as f:
        issues = json.load(f)
    # Take random sample
    sample = random.sample(issues, min(sample_size, len(issues)))
    golden = []
    for issue in sample:
        gold_label = map_labels_to_type(issue["labels"])
        golden.append({
            "id": issue["id"],
            "title": issue["title"],
            "body": issue["body"][:1000],  # truncate
            "true_label": gold_label,
            "raw_labels": issue["labels"]
        })
    with open(output_file, "w") as f:
        json.dump(golden, f, indent=2)
    print(f"Golden set saved to {output_file} with {len(golden)} examples")
    return golden

if __name__ == "__main__":
    create_golden_set("data_pipeline/pandas_issues.json", "evals/golden_sets/classification_golden.json")