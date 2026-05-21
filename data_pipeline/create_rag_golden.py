import json
import random
from pathlib import Path

from app.core.config import settings
from app.infra.ai_clients import GeminiClient, ProviderError

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_PATH = REPO_ROOT / "data_pipeline" / "knowledge_base.json"
OUTPUT_PATH = REPO_ROOT / "evals" / "golden_sets" / "rag_golden.json"


with KB_PATH.open(encoding="utf-8") as f:
    kb = json.load(f)

if not settings.gemini_api_key:
    raise RuntimeError("Set GEMINI_API_KEY in .env before running this script.")

client = GeminiClient(
    api_key=settings.gemini_api_key,
    model=settings.gemini_model,
    timeout_seconds=settings.provider_timeout_seconds,
)

golden = []
# take 30 random issues to generate Q&A pairs, then select 25
sample = random.sample(kb, min(30, len(kb)))
for item in sample:
    prompt = f"""Based on the following GitHub issue, generate a realistic user question that this issue would answer, and provide the answer in one sentence.
Issue title: {item['title']}
Issue body: {item['body'][:500]}
Return in format: QUESTION: ... ANSWER: ..."""
    try:
        response_text = client.generate_text(prompt)
    except ProviderError as exc:
        print(f"Skipping issue {item['id']}: {exc}")
        continue

    # parse simple
    if "QUESTION:" in response_text and "ANSWER:" in response_text:
        q_part = response_text.split("QUESTION:", 1)[1].split("ANSWER:", 1)[0].strip()
        a_part = response_text.split("ANSWER:", 1)[1].strip()
        golden.append(
            {
                "question": q_part,
                "answer": a_part,
                "ground_truth_doc_id": item["id"],
                "context": item["title"] + "\n" + item["body"],
            }
        )
    if len(golden) >= 25:
        break

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_PATH.open("w", encoding="utf-8") as f:
    json.dump(golden, f, indent=2)
print(f"Saved {len(golden)} RAG golden QA pairs")
