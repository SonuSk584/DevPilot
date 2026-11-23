
import re
from rank_bm25 import BM25Okapi


class BM25CodeRetriever:
    """
    Keyword-based retrieval for Python code chunks,
    with separate indexes for different repositories.
    """

    def __init__(self):
        self.repository_chunks = {}
        self.repository_indexes = {}

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """
        Split code into searchable tokens.
        """

        tokens = re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*|\d+",
            text.lower()
        )

        expanded_tokens = []

        for token in tokens:
            expanded_tokens.append(token)

            # Split snake_case identifiers.
            expanded_tokens.extend(
                part for part in token.split("_") if part
            )

            # Split identifier components.
            identifier_parts = re.findall(
                r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+",
                token
            )

            expanded_tokens.extend(
                part.lower()
                for part in identifier_parts
                if part
            )

        return expanded_tokens

    def index_chunks(
        self,
        chunks: list[dict],
        repository_id: str,
    ) -> int:
        """
        Build a separate BM25 index for one repository.
        """

        if not repository_id or not repository_id.strip():
            raise ValueError("Repository ID cannot be empty.")

        if not chunks:
            self.repository_chunks.pop(repository_id, None)
            self.repository_indexes.pop(repository_id, None)
            return 0

        tokenized_documents = [
            self.tokenize(
                f"{chunk.get('symbol_name') or ''} "
                f"{chunk.get('file_path', '')} "
                f"{chunk.get('content', '')}"
            )
            for chunk in chunks
        ]

        self.repository_chunks[repository_id] = chunks
        self.repository_indexes[repository_id] = BM25Okapi(
            tokenized_documents
        )

        return len(chunks)

    def search(
        self,
        query: str,
        repository_id: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Search only the BM25 index belonging to one repository.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if not repository_id or not repository_id.strip():
            raise ValueError("Repository ID cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        bm25 = self.repository_indexes.get(repository_id)

        if bm25 is None:
            return []

        query_tokens = self.tokenize(query)

        if not query_tokens:
            return []

        chunks = self.repository_chunks[repository_id]
        scores = bm25.get_scores(query_tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True
        )

        results = []

        for index in ranked_indices:
            chunk = chunks[index]

            document_tokens = self.tokenize(
                f"{chunk.get('symbol_name') or ''} "
                f"{chunk.get('file_path', '')} "
                f"{chunk.get('content', '')}"
            )

    # Skip documents with no matching query tokens.
            if not set(query_tokens).intersection(document_tokens):
                continue

            result = chunk.copy()
            result["bm25_score"] = float(scores[index])

            results.append(result)

            if len(results) >= top_k:
                break

        return results
