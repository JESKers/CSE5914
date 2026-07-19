"""Minimal local-LLM hello world for the rag package.

This uses a local Ollama model and does not require an API key.
"""
from langchain_core.messages import HumanMessage

try:
    from .ollama_utils import get_chat_model
except ImportError:  # pragma: no cover - allows direct script execution
    from ollama_utils import get_chat_model


def main() -> None:
    # This is a tiny smoke test to make sure the local model is reachable.
    prompt = "Reply with one sentence confirming the JESKers car recommender LLM is online."
    llm = get_chat_model(temperature=0.0)
    response = llm.invoke([HumanMessage(content=prompt)])
    text = response.content if hasattr(response, "content") else str(response)
    print(text)


if __name__ == "__main__":
    main()
