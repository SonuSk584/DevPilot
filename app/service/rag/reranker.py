
from fastembed.rerank.cross_encoder import TextCrossEncoder


MODEL_NAME = "jinaai/jina-reranker-v1-turbo-en"

# Load the reranking model once.
reranker_model = TextCrossEncoder(
    model_name=MODEL_NAME
)


def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank retrieved code chunks according to their
    relevance to the original query.
    """

    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    if not chunks:
        return []

    documents = [
        (
            f"File: {chunk.get('file_path', '')}\n"
            f"Symbol: {chunk.get('symbol_name', '')}\n"
            f"Code:\n{chunk.get('content', '')}"
        )
        for chunk in chunks
    ]

    scores = reranker_model.rerank(
        query,
        documents,
    )

    ranked_results = []

    for index, score in enumerate(scores):
        chunk = chunks[index].copy()

        chunk["rerank_score"] = float(score)

        ranked_results.append(chunk)

    ranked_results.sort(
        key=lambda item: item["rerank_score"],
        reverse=True,
    )

    return ranked_results[:top_k]
