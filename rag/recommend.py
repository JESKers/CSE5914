"""Simple local Ollama-based RAG entry point for the rag package.

This intentionally avoids any API key and uses local models via Ollama.
It can work with a simple CSV/JSON dataset or later be connected to Elasticsearch.
"""
import os
from pathlib import Path

from langchain_community.vectorstores import FAISS

try:
    from .ollama_utils import get_chat_model, get_embeddings
except ImportError:  # pragma: no cover - allows direct script execution
    from ollama_utils import get_chat_model, get_embeddings

ROOT = Path(__file__).resolve().parent.parent
DATASET = Path(__file__).resolve().parent / "data_small.csv"
INDEX_DIR = Path(__file__).resolve().parent / "faiss_index"

PROMPT_TEMPLATE = """
Human: You are an AI assistant that answers questions using the provided context.
Use only the provided information when possible.
If you don't know the answer, say that you don't know.

<context>
{context}
</context>

<question>
{question}
</question>

Assistant:"""


def index_exists() -> bool:
    return (INDEX_DIR / "index.faiss").exists() and (INDEX_DIR / "index.pkl").exists()


def build_demo_index():
    """Create a minimal FAISS index from the ragllm demo CSV if available."""
    if not DATASET.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET}")

    from langchain_community.document_loaders import CSVLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    loader = CSVLoader(file_path=str(DATASET))
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    docs = text_splitter.split_documents(documents)

    embeddings = get_embeddings()
    store = FAISS.from_documents(docs, embeddings)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(INDEX_DIR))
    return store


def load_index():
    embeddings = get_embeddings()
    return FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def make_chain(vectorstore=None):
    llm = get_chat_model()
    retriever = (vectorstore or load_index()).as_retriever()

    def chain(question: str) -> str:
        docs = retriever.invoke(question)
        context = format_docs(docs)
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    return chain


def recommend(query: str, rebuild: bool = False):
    if rebuild or not index_exists():
        build_demo_index()
    chain = make_chain()
    return chain(query)


if __name__ == "__main__":
    query = os.getenv("QUERY", "What is the difference between the skittles flavors?")
    print(recommend(query, rebuild=os.getenv("REBUILD_INDEX", "false").lower() == "true"))
