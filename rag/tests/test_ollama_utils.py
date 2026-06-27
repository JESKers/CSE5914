import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ollama_utils import LocalOllamaEmbeddings


def test_embed_documents_uses_batch_payload():
    embeddings = LocalOllamaEmbeddings(model="demo", base_url="http://localhost:11434")
    assert embeddings._normalize_input(["hello", "world"]) == ["hello", "world"]
