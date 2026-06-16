import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import jsonschema
from jsonschema import validate
from elasticsearch import Elasticsearch

# Database Connection Setup 
# Pulling the credentials injected by your docker-compose.yml
ES_HOST = os.getenv("ES_HOST", "https://localhost:9200")
ES_USER = os.getenv("ES_USER", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "changeme")

# Initialize the Elasticsearch client
# Note: verify_certs=False is used here because local Docker uses self-signed certificates
es_client = Elasticsearch(
    [ES_HOST],
    basic_auth=(ES_USER, ES_PASSWORD),
    verify_certs=False, 
    ssl_show_warn=False
)

# API Initialization
app = FastAPI(title="Smart Car Recommendation API")

# The strict JSON schema
car_schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["make", "model", "year", "msrp"],
    "properties": {
        "make": {"type": "string"},
        "model": {"type": "string"},
        "year": {"type": "integer"},
        "msrp": {"type": "integer"}
    }
}


@app.get("/api/health")
async def health_check():
    """
    A quick endpoint to verify that your API can talk to Kangjie's database.
    """
    try:
        # Ping the Elasticsearch cluster
        cluster_info = es_client.info()
        return {
            "status": "connected",
            "cluster_name": cluster_info.get("cluster_name"),
            "elasticsearch_version": cluster_info.get("version", {}).get("number")
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")


@app.post("/api/search")
async def process_search(payload: dict):
    """
    The main integration hub.
    """
    try:
        # Validate the incoming data from the frontend
        validate(instance=payload, schema=car_schema)
        
        # querying Elasticsearch 
        # (Kangjie will give the exact query structure he wants to use later)
        # response = es_client.search(
        #     index="cars_index",
        #     body={
        #         "query": {
        #             "match": {"make": payload["make"]}
        #         }
        #     }
        # )
        
        # Pass the response to RAG-LLM
        
        return {
            "status": "success", 
            "message": "Data validated securely!", 
            "received_payload": payload
        }
        
    except jsonschema.exceptions.ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Data validation failed: {e.message}")