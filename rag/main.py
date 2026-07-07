"""Simple local RAG entry point for the rag package."""
# This is the small front door for the local RAG flow.
# It keeps things easy to run and makes the recommender feel like a simple demo.
from recommend import recommend

if __name__ == "__main__":
    # The example query is intentionally basic so it is easy to swap out.
    query = "What is the difference between the skittles flavors?"
    print(recommend(query, rebuild=False))
