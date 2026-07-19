import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ollama_utils import LocalOllamaEmbeddings, get_ollama_config


def test_embed_documents_uses_batch_payload():
    embeddings = LocalOllamaEmbeddings(model="demo", base_url="http://localhost:11434")
    assert embeddings._normalize_input(["hello", "world"]) == ["hello", "world"]


def test_get_ollama_config_uses_compose_service_host_when_running_in_container(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("container", "docker")
    monkeypatch.setattr("ollama_utils.os.path.exists", lambda path: path == "/.dockerenv")

    assert get_ollama_config()["base_url"] == "http://ollama:11434"
