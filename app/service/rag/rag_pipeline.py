
from app.service.rag.vector_store import get_repository_chunks
from app.service.rag.bm25_retriever import BM25CodeRetriever
from app.service.rag.hybrid_retriever import HybridRetriever


def retrieve_relevant_chunks(
    query: str,
    repository_id: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve relevant repository code using hybrid search
    and cross-encoder reranking.

    BM25 is rebuilt from persistent ChromaDB data so retrieval
    continues to work after DevPilot restarts.
    """

    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if not repository_id or not repository_id.strip():
        raise ValueError("Repository ID cannot be empty.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    # 1. Load repository chunks from persistent ChromaDB.
    chunks = get_repository_chunks(repository_id)

    if not chunks:
        return []

    # 2. Rebuild the repository-specific BM25 index.
    bm25_retriever = BM25CodeRetriever()

    bm25_retriever.index_chunks(
        chunks=chunks,
        repository_id=repository_id,
    )

    # 3. Initialize hybrid retrieval.
    hybrid_retriever = HybridRetriever(
        bm25_retriever=bm25_retriever
    )

    # 4. Retrieve and rerank relevant chunks.
    return hybrid_retriever.search(
        query=query,
        repository_id=repository_id,
        top_k=top_k,
    )
