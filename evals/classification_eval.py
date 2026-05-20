import json
import requests
from sklearn.metrics import accuracy_score, f1_score, classification_report
import os

MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://localhost:8001")

def evaluate_classification(golden_set_path, model_name="rule"):
    with open(golden_set_path) as f:
        golden = json.load(f)
    
    y_true = []
    y_pred = []
    
    for item in golden:
        response = requests.post(
            f"{MODEL_SERVER_URL}/classify",
            json={"title": item["title"], "body": item["body"], "model": model_name}
        )
        if response.status_code != 200:
            print(f"Error for {item['id']}: {response.text}")
            continue
        pred = response.json()["label"]
        y_true.append(item["true_label"])
        y_pred.append(pred)
    
    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="weighted")
    report = classification_report(y_true, y_pred)
    
    result = {
        "model": model_name,
        "accuracy": acc,
        "f1_weighted": f1,
        "detailed_report": report,
        "num_samples": len(y_true)
    }
    return result

if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "rule"
    result = evaluate_classification("evals/golden_sets/classification_golden.json", model)
    print(json.dumps(result, indent=2))
    # Save to file
    with open("evals/classification_report.json", "w") as f:
        json.dump(result, f, indent=2)