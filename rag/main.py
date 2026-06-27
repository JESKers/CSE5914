"""Simple local RAG entry point for the rag package."""
from recommend import recommend

if __name__ == "__main__":
    query = "What is the difference between the skittles flavors?"
    print(recommend(query, rebuild=False))
