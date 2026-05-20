import google.generativeai as genai

class RuleClassifier:
    def predict(self, title, body):
        text = (title + " " + body).lower()
        if any(w in text for w in ["bug", "crash", "error", "wrong", "fix"]):
            return "bug"
        if any(w in text for w in ["feature", "add", "new", "enhance", "improve"]):
            return "feature"
        if any(w in text for w in ["doc", "tutorial", "readme", "example"]):
            return "docs"
        if any(w in text for w in ["question", "how", "why", "?"]):
            return "question"
        return "other"

class GeminiZeroShotClassifier:
    def __init__(self, api_key, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def predict(self, title, body):
        prompt = f"""Classify the following GitHub issue into exactly one of: bug, feature, docs, question, other.
Title: {title}
Body: {body[:500]}
Answer only with the category name."""
        response = self.model.generate_content(prompt)
        label = response.text.strip().lower()
        if label not in ["bug", "feature", "docs", "question", "other"]:
            return "other"
        return label

class GeminiFewShotClassifier:
    def __init__(self, api_key, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.examples = [
            ("RuntimeError: index out of bounds", "bug"),
            ("Add support for parquet file format", "feature"),
            ("Improve API reference documentation", "docs"),
            ("How to filter DataFrame with multiple conditions?", "question"),
        ]
    
    def predict(self, title, body):
        example_str = "\n".join([f"Example: {ex[0]} -> {ex[1]}" for ex in self.examples])
        prompt = f"""{example_str}
Classify this issue:
Title: {title}
Body: {body[:500]}
Category (bug/feature/docs/question/other):"""
        response = self.model.generate_content(prompt)
        label = response.text.strip().lower()
        if label not in ["bug", "feature", "docs", "question", "other"]:
            return "other"
        return label
