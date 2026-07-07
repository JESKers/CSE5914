"""Helpers for using local Ollama models from the rag package."""
import os
from typing import List

import requests
from langchain_core.embeddings import Embeddings


class OllamaChatModel:
    """Small wrapper around the local Ollama chat API."""
    # This wrapper keeps the Ollama request details in one tidy place.

    def __init__(self, model: str, base_url: str, temperature: float = 0.2):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    def _extract_text(self, message) -> str:
        if hasattr(message, "content"):
            content = message.content
            if isinstance(content, list):
                return "\n".join(str(item) for item in content)
            return str(content)
        return str(message)

    def invoke(self, messages):
        # The model call is intentionally simple, which makes it easier to swap in another backend later.
        if isinstance(messages, str):
            prompt = messages
        else:
            prompt = "\n".join(self._extract_text(message) for message in messages)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return type("Response", (), {"content": data.get("response", "")})()


class LocalOllamaEmbeddings(Embeddings):
    """Embeddings adapter for local Ollama."""
    # Embeddings are batched here so the requests stay manageable and predictable.

    def __init__(self, model: str, base_url: str, batch_size: int = 8):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size

    def _normalize_input(self, texts: List[str]) -> List[str]:
        return [str(text).strip() for text in texts if str(text).strip()]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        normalized = self._normalize_input(texts)
        if not normalized:
            return []

        all_embeddings: List[List[float]] = []
        for start in range(0, len(normalized), self.batch_size):
            batch = normalized[start:start + self.batch_size]
            payload = {"model": self.model, "input": batch}
            resp = requests.post(f"{self.base_url}/api/embed", json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if len(embeddings) != len(batch):
                raise ValueError(f"Expected {len(batch)} embeddings, got {len(embeddings)}")
            all_embeddings.extend(embeddings)
        return all_embeddings


def get_ollama_config() -> dict:
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "chat_model": os.getenv("OLLAMA_CHAT_MODEL", "llama3.2"),
        "embedding_model": os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    }


def get_chat_model(temperature: float = 0.2):
    cfg = get_ollama_config()
    return OllamaChatModel(
        model=cfg["chat_model"],
        base_url=cfg["base_url"],
        temperature=temperature,
    )


def get_embeddings():
    cfg = get_ollama_config()
    return LocalOllamaEmbeddings(
        model=cfg["embedding_model"],
        base_url=cfg["base_url"],
    )