
import chromadb
from pathlib import Path


# Persistent database location
VECTOR_DB_PATH = Path("data/chroma_db")

client = chromadb.PersistentClient(
    path=str(VECTOR_DB_PATH)
)

collection = client.get_or_create_collection(
    name="devpilot_code",
    metadata={"hnsw:space": "cosine"}
)


def store_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
    repository_id: str,
) -> int:
    """
    Store code chunks and their embeddings in ChromaDB,
    keeping different repositories isolated.
    """

    if not repository_id or not repository_id.strip():
        raise ValueError("Repository ID cannot be empty.")

    if len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings must have the same length.")

    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for chunk, embedding in zip(chunks, embeddings):

        original_chunk_id = chunk["chunk_id"]

        # Make chunk IDs globally unique across repositories.
        unique_chunk_id = f"{repository_id}::{original_chunk_id}"

        ids.append(unique_chunk_id)
        documents.append(chunk["content"])

        metadatas.append({
            "repository_id": repository_id,
            "chunk_id": original_chunk_id,
            "file_path": chunk["file_path"],
            "chunk_type": chunk["chunk_type"],
            "symbol_name": chunk["symbol_name"] or "",
            "line_start": chunk["line_start"],
            "line_end": chunk["line_end"],
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return len(ids)


def search_chunks(
    query_embedding: list[float],
    repository_id: str,
    top_k: int = 5,
) -> dict:
    """
    Retrieve semantically similar chunks from one repository only.
    """

    if not query_embedding:
        raise ValueError("Query embedding cannot be empty.")

    if not repository_id or not repository_id.strip():
        raise ValueError("Repository ID cannot be empty.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"repository_id": repository_id},
        include=["documents", "metadatas", "distances"],
    )

    return results


def delete_file_chunks(
    file_path: str,
    repository_id: str,
) -> int:
    """
    Delete chunks belonging to a specific file
    within a specific repository.
    """

    existing = collection.get(
        where={
            "$and": [
                {"repository_id": repository_id},
                {"file_path": file_path},
            ]
        },
        include=[],
    )

    ids = existing["ids"]

    if ids:
        collection.delete(ids=ids)

    return len(ids)

def get_repository_chunks(repository_id: str) -> list[dict]:
    """
    Retrieve all stored code chunks belonging to a repository.
    Used to rebuild the in-memory BM25 index.
    """

    if not repository_id or not repository_id.strip():
        raise ValueError("Repository ID cannot be empty.")

    results = collection.get(
        where={"repository_id": repository_id},
        include=["documents", "metadatas"],
    )

    chunks = []

    for index, metadata in enumerate(results["metadatas"]):
        chunks.append({
            "chunk_id": metadata["chunk_id"],
            "file_path": metadata["file_path"],
            "chunk_type": metadata["chunk_type"],
            "symbol_name": metadata["symbol_name"],
            "line_start": metadata["line_start"],
            "line_end": metadata["line_end"],
            "content": results["documents"][index],
        })

    return chunks

def get_repository_file_paths(repository_id: str) -> set[str]:
    """
    Return all file paths currently indexed for a repository.
    """

    if not repository_id or not repository_id.strip():
        raise ValueError("Repository ID cannot be empty.")

    results = collection.get(
        where={"repository_id": repository_id},
        include=["metadatas"],
    )

    return {
        metadata["file_path"]
        for metadata in results["metadatas"]
    }