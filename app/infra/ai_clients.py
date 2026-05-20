import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    pass


def _request_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers, method="POST")

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_response = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"{url} failed with HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise ProviderError(f"{url} request failed: {exc.reason}") from exc

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"{url} returned invalid JSON") from exc


@dataclass(slots=True)
class GeminiClient:
    api_key: str
    model: str = "gemini-2.5-flash"
    timeout_seconds: float = 30.0

    def generate_text(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
            },
        }
        response = _request_json(
            url,
            {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            payload,
            self.timeout_seconds,
        )

        candidates = response.get("candidates", [])
        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            chunks = [part.get("text", "") for part in parts if part.get("text")]
            if chunks:
                return "".join(chunks).strip()

        raise ProviderError("Gemini returned no text candidate")


@dataclass(slots=True)
class VoyageClient:
    api_key: str
    model: str = "voyage-code-2"
    timeout_seconds: float = 30.0

    def embed_text(self, text: str, input_type: str = "query") -> list[float]:
        url = "https://api.voyageai.com/v1/embeddings"
        payload = {
            "input": text,
            "model": self.model,
            "input_type": input_type,
        }
        response = _request_json(
            url,
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            payload,
            self.timeout_seconds,
        )

        data = response.get("data", [])
        if not data:
            raise ProviderError("Voyage returned no embeddings")

        embedding = data[0].get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise ProviderError("Voyage embedding payload was empty")

        return [float(value) for value in embedding]
