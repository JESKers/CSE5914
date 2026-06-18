import os
import bs4
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.document_loaders import CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Create a WebBaseLoader instance to load documents from web sources
# loader = WebBaseLoader(
#     web_paths=(
#         "https://en.wikipedia.org/wiki/Skittles_(confectionery)",
#     ),
# )

loader = CSVLoader(
    # file_path="data.csv"
    file_path="data_small.csv"
)

# Load documents from sources using the loader
documents = loader.load()
# Initialize a RecursiveCharacterTextSplitter for splitting text into chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)

# Split the documents into chunks using the text_splitter
docs = text_splitter.split_documents(documents)
# Let's see how many chunks we created
print(len(docs))
# Let's take a look at the first document
print(docs[1])

# Embedding
from langchain_milvus import Milvus
from langchain_ollama import OllamaEmbeddings

ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
rebuild_index = os.getenv("REBUILD_INDEX", "FALSE").upper() == "TRUE"

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=ollama_base_url,
)

# Set to true when the csv changes, otherwise it doesn't re embed the csv every time
BUILD_INDEX = False

if BUILD_INDEX:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
    )
    docs = text_splitter.split_documents(documents)

    vectorstore = Milvus.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="car_data",
        connection_args={"uri": "./car_data.db"},
        drop_old=True,
    )
else:
    vectorstore = Milvus(
        embedding_function=embeddings,
        collection_name="car_data",
        connection_args={"uri": "./car_data.db"},
    )

# Prompt Template
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

# Initialize the OpenAI language model for response generation
# Set temperature to 0.2 to make the responses more consistant
llm = ChatOllama(
    model=ollama_model,
    base_url=ollama_base_url,
    temperature=0.2,
)

# Define the prompt template for generating AI responses
PROMPT_TEMPLATE = """
Human: You are an AI assistant, and provides answers to questions by using fact based and statistical information when possible.
Use the following pieces of information to provide a concise answer to the question enclosed in <question> tags.
If you don't know the answer, just say that you don't know, don't try to make up an answer.
<context>
{context}
</context>

<question>
{question}
</question>

The response should be specific and use statistics or numbers when possible.

Assistant:"""

# Create a PromptTemplate instance with the defined template and input variables
prompt = PromptTemplate(
    template=PROMPT_TEMPLATE, input_variables=["context", "question"]
)
# Convert the vector store to a retriever
retriever = vectorstore.as_retriever()

# Define a function to format the retrieved documents
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


# Prompting
# Define the RAG (Retrieval-Augmented Generation) chain for AI response generation
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# rag_chain.get_graph().print_ascii()

# query="can you give me 3 of the lowest costing car with above 30mpg mileage"
# query="can you give me 3 all terraine car, and it should have relatively modern interface"
query="What's the different flavors of skittles"

# retrieved_docs = retriever.invoke(query)

# print("Retrieved Docs\n")
# for i, doc in enumerate(retrieved_docs):
#     print(f"\n--- DOC {i + 1} ---")
#     print(doc.page_content)

# Invoke the RAG chain with a specific question and retrieve the response
res = rag_chain.invoke(query)

print(res)