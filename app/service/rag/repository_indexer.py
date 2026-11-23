
from pathlib import Path

from app.service.repository_scanner import scan_repository
from app.service.source_extractor import extract_source_code

from app.service.rag.code_indexer import index_python_file
from app.service.rag.code_chunker import chunk_python_file
from app.service.rag.embedding_service import generate_embeddings
from app.service.rag.vector_store import (
    store_chunks,
    delete_file_chunks,
    get_repository_file_paths,
)


def index_repository(root_path: str) -> dict:
    """
    Scan a repository, extract Python source code, create AST-based
    chunks, generate embeddings, and refresh its ChromaDB index.
    """

    root = Path(root_path).resolve()

    if not root.exists() or not root.is_dir():
        raise ValueError(f"Invalid repository path: {root_path}")

    repository_id = str(root)

    # 1. Get previously indexed files.
    existing_files = get_repository_file_paths(repository_id)

    # 2. Scan repository files.
    file_paths = scan_repository(str(root))

    current_python_paths = {
        path for path in file_paths
        if Path(path).suffix.lower() == ".py"
    }

    # 3. Extract Python source code.
    source_files = extract_source_code(
        str(root),
        file_paths,
    )
    extracted_paths = {
        source_file["path"]
        for source_file in source_files
    }

    extraction_failed_files = current_python_paths - extracted_paths

    all_chunks = []
    indexed_files = []
    failed_files = [
    {
        "file_path": file_path,
        "error": "Source extraction failed: file could not be read or decoded.",
    }
    for file_path in sorted(extraction_failed_files)
]

    # 4. Index and chunk each Python file.
    for source_file in source_files:
        file_path = source_file["path"]
        content = source_file["content"]

        ast_result = index_python_file(file_path, content)

        if ast_result["status"] != "success":
            failed_files.append({
                "file_path": file_path,
                "error": ast_result.get("error", "AST indexing failed"),
            })
            continue

        chunk_result = chunk_python_file(file_path, content)

        if chunk_result["status"] != "success":
            failed_files.append({
                "file_path": file_path,
                "error": chunk_result.get("error", "Code chunking failed"),
            })
            continue

        all_chunks.extend(chunk_result["chunks"])
        indexed_files.append(file_path)

    # 5. Generate embeddings before deleting existing data.
    embeddings = []

    if all_chunks:
        texts = [chunk["content"] for chunk in all_chunks]
        embeddings = generate_embeddings(texts)

    # 6. Delete old chunks for successfully indexed files.
    for file_path in indexed_files:
        delete_file_chunks(file_path, repository_id)

    # 7. Delete chunks belonging to files removed from the repository.
    deleted_files = existing_files - current_python_paths

    for file_path in deleted_files:
        delete_file_chunks(file_path, repository_id)

    # 8. Store refreshed chunks.
    if all_chunks:
        stored_count = store_chunks(
            chunks=all_chunks,
            embeddings=embeddings,
            repository_id=repository_id,
        )
    else:
        stored_count = 0

    return {
        "repository_id": repository_id,
        "repository_path": str(root),
        "total_files_scanned": len(file_paths),
        "python_files_extracted": len(source_files),
        "files_indexed": len(indexed_files),
        "files_failed": len(failed_files),
        "total_chunks": len(all_chunks),
        "stored_chunks": stored_count,
        "indexed_files": indexed_files,
        "failed_files": failed_files,
        "deleted_files": sorted(deleted_files),
        "status": "success",
    }
