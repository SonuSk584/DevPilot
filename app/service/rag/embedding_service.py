
from fastembed import TextEmbedding


MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"

# Load the model once and reuse it.
embedding_model = TextEmbedding(
    model_name=MODEL_NAME
)


def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding for a single text or code chunk.
    """

    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    embedding = next(
        embedding_model.embed([text])
    )

    return embedding.tolist()


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple text or code chunks.
    """

    if not texts:
        return []

    if any(not text or not text.strip() for text in texts):
        raise ValueError("Texts cannot contain empty values.")

    embeddings = embedding_model.embed(texts)

    return [
        embedding.tolist()
        for embedding in embeddings
    ]
