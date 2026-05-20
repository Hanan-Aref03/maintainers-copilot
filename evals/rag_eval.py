import json
import asyncio
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness, context_recall
from datasets import Dataset
from app.services.rag_service import retrieve_context
from app.core.config import settings
import os

# Set Gemini key for RAGAS (it may use OpenAI by default, so we need to customize)
# For simplicity, we'll implement a custom metric using Gemini. But to save time,
# we'll use a simple recall@k metric based on ground truth doc ID.

async def evaluate_rag(golden_path: str, k: int = 3):
    with open(golden_path) as f:
        golden = json.load(f)
    
    retrieved_ids = []
    for item in golden:
        docs = await retrieve_context(item["question"], top_k=k)
        retrieved_ids.append([doc["id"] for doc in docs])
    
    hits = 0
    for i, item in enumerate(golden):
        if item["ground_truth_doc_id"] in retrieved_ids[i]:
            hits += 1
    recall = hits / len(golden)
    result = {
        "recall_at_k": recall,
        "k": k,
        "hits": hits,
        "total": len(golden)
    }
    return result

if __name__ == "__main__":
    result = asyncio.run(evaluate_rag("evals/golden_sets/rag_golden.json"))
    print(json.dumps(result, indent=2))
    with open("evals/rag_report.json", "w") as f:
        json.dump(result, f, indent=2)