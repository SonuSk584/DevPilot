
from app.service.rag.embedding_service import generate_embedding
from app.service.rag.vector_store import search_chunks
from app.service.rag.bm25_retriever import BM25CodeRetriever
from app.service.rag.reranker import rerank_chunks


class HybridRetriever:
    """
    Combines semantic search and BM25 keyword search
    using Reciprocal Rank Fusion (RRF), followed by
    cross-encoder reranking.
    """

    def __init__(
        self,
        bm25_retriever: BM25CodeRetriever,
        rrf_k: int = 60,
    ):
        self.bm25_retriever = bm25_retriever
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        repository_id: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Retrieve relevant chunks using hybrid search
        and rerank them using a cross-encoder.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if not repository_id or not repository_id.strip():
            raise ValueError("Repository ID cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        # Retrieve more candidates before fusion and reranking.
        candidate_count = max(top_k * 3, 10)

        # 1. Semantic retrieval.
        query_embedding = generate_embedding(query)

        semantic_results = search_chunks(
            query_embedding=query_embedding,
            repository_id=repository_id,
            top_k=candidate_count,
        )

        # 2. Keyword retrieval.
        keyword_results = self.bm25_retriever.search(
            query=query,
            repository_id=repository_id,
            top_k=candidate_count,
        )

        semantic_chunk_ids = [
            metadata["chunk_id"]
            for metadata in semantic_results["metadatas"][0]
        ]

        # 3. Reciprocal Rank Fusion.
        fused_results = {}

        for result_list in (
            semantic_chunk_ids,
            [result["chunk_id"] for result in keyword_results],
        ):
            for rank, chunk_id in enumerate(result_list, start=1):
                if chunk_id not in fused_results:
                    fused_results[chunk_id] = {
                        "chunk_id": chunk_id,
                        "rrf_score": 0.0,
                    }

                fused_results[chunk_id]["rrf_score"] += (
                    1.0 / (self.rrf_k + rank)
                )

        # 4. Sort by combined RRF score.
        ranked_results = sorted(
            fused_results.values(),
            key=lambda item: item["rrf_score"],
            reverse=True,
        )

        # 5. Build lookup dictionaries.
        keyword_lookup = {
            result["chunk_id"]: result
            for result in keyword_results
        }

        semantic_lookup = {}

        semantic_metadatas = semantic_results["metadatas"][0]
        semantic_documents = semantic_results["documents"][0]

        for index, chunk_id in enumerate(semantic_chunk_ids):
            metadata = semantic_metadatas[index]

            semantic_lookup[chunk_id] = {
                "content": semantic_documents[index],
                "file_path": metadata["file_path"],
                "chunk_type": metadata["chunk_type"],
                "symbol_name": metadata["symbol_name"],
                "line_start": metadata["line_start"],
                "line_end": metadata["line_end"],
            }

        # 6. Build the candidate pool for reranking.
        candidate_results = []

        for result in ranked_results[:candidate_count]:
            chunk_id = result["chunk_id"]

            chunk = (
                keyword_lookup.get(chunk_id)
                or semantic_lookup.get(chunk_id)
            )

            if chunk is None:
                continue

            candidate_results.append({
                **chunk,
                "chunk_id": chunk_id,
                "repository_id": repository_id,
                "rrf_score": result["rrf_score"],
            })

        # 7. Rerank candidates using the cross-encoder.
        final_results = rerank_chunks(
            query=query,
            chunks=candidate_results,
            top_k=top_k,
        )

        return final_results
