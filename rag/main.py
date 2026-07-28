"""Simple local RAG entry point for the rag package."""
# This is the small front door for the local RAG flow.
# It keeps things easy to run and makes the recommender feel like a simple demo.
from recommend import recommend

if __name__ == "__main__":
    query = "Find a fuel-efficient SUV under $40,000"
    print(recommend(query, rebuild=False))
