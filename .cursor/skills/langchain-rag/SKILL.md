---
name: langchain-rag
description: Builds retrieval-augmented generation pipelines with document loaders, text splitters, embeddings, and vector stores. Use when indexing documents, implementing KB search, or wiring RAG into agents.
---

# LangChain RAG

**Pipeline:** Load → Split → Embed → Store → Retrieve → Generate

## End-to-end (Python)

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

docs = [
    Document(page_content="LangChain is a framework for LLM apps.", metadata={}),
    Document(page_content="RAG = Retrieval Augmented Generation.", metadata={}),
]

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
splits = splitter.split_documents(docs)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = InMemoryVectorStore.from_documents(splits, embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

query = "What is RAG?"
relevant = retriever.invoke(query)
context = "\n\n".join(d.page_content for d in relevant)

model = ChatOpenAI(model="gpt-4.1")
response = model.invoke([
    {"role": "system", "content": f"Use this context:\n\n{context}"},
    {"role": "user", "content": query},
])
```

## Vector store selection

| Store | Use case |
|-------|----------|
| InMemory | Testing only |
| FAISS | Local, fast |
| Chroma | Dev, persistent |
| Pinecone | Production, managed |

Use dedicated packages: `langchain-chroma`, not `langchain_community.vectorstores.Chroma`.

## Document loaders

```python
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader, DirectoryLoader, TextLoader

docs = PyPDFLoader("./doc.pdf").load()
docs = WebBaseLoader("https://example.com").load()
docs = DirectoryLoader("path/to/docs", glob="**/*.md", loader_cls=TextLoader).load()
```

For markdown KB folders, loading whole files often beats aggressive chunking when docs are small and similar.

## Text splitting

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,  # 10-20% of chunk_size
    separators=["\n\n", "\n", " ", ""],
)
splits = splitter.split_documents(docs)
```

## Persistent Chroma

```python
from langchain_chroma import Chroma

vectorstore = Chroma.from_documents(
    splits,
    OpenAIEmbeddings(),
    persist_directory="./chroma_db",
    collection_name="my-collection",
)
```

## Retrieval options

```python
# Similarity
results = vectorstore.similarity_search(query, k=5)

# With scores
for doc, score in vectorstore.similarity_search_with_score(query, k=5):
    print(score, doc.page_content[:80])

# MMR (diversity)
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"fetch_k": 20, "lambda_mult": 0.5, "k": 5},
)

# Metadata filter
results = vectorstore.similarity_search(query, k=5, filter={"category": "policy"})
```

## RAG as agent tool

```python
from langchain.agents import create_agent
from langchain_core.tools import tool

@tool
def search_docs(query: str) -> str:
    """Search company knowledge base for policies, specs, and procedures."""
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)

agent = create_agent(model="gpt-4.1", tools=[search_docs])
```

## Common mistakes

| Wrong | Correct |
|-------|---------|
| `chunk_size=50` or `10000` | `1000` with `overlap=200` |
| `chunk_overlap=0` | 10-20% overlap |
| InMemory in production | Chroma/FAISS/Pinecone with persistence |
| Different embed models for index vs query | Same `OpenAIEmbeddings(model=...)` everywhere |
| `FAISS.load_local` without flag | `allow_dangerous_deserialization=True` |

## Metadata pattern (this repo)

Attach `doc_id`, `category`, `title` from `kb_index.py` when indexing KB docs — enables filtered retrieval by document type.
