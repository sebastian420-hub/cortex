"""
Semantic Memory Manager using ChromaDB for vector storage and retrieval.

This module provides an interface for storing and querying text embeddings,
acting as a long-term semantic memory for the Cortex agent.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    import chromadb
    from chromadb.utils import embedding_functions
    from chromadb.api.models import Collection
except ImportError:
    chromadb = None
    embedding_functions = None
    Collection = None

from .embeddings import (
    BaseEmbeddingModel,
    LocalEmbeddingModel,
)  # Assuming LocalEmbeddingModel is the default

logger = logging.getLogger(__name__)

# ---- how entries are ranked and aged -------------------------------------------------------
# Decay is computed when an entry is read, from its timestamps; nothing runs in the background
# and nothing is written back, so an entry that was not touched keeps exactly what it was given.
HALF_LIFE_DAYS = 30.0  # an unverified entry counts for half as much after this long
# score = similarity, plus how much the entry is trusted, plus how recently it was confirmed
WEIGHT_SIMILARITY = 0.6
WEIGHT_CONFIDENCE = 0.2
WEIGHT_RECENCY = 0.2
VERIFY_BOOST = 0.1  # confidence gained when something confirms an entry
VERIFY_PENALTY = 0.3  # confidence lost when something contradicts it
CONFIDENCE_FLOOR = 0.1
DEFAULT_CONFIDENCE = 0.5
CANDIDATE_FACTOR = 4  # fetch this many times top_k by similarity, then re-rank


def normalize_text(text: str) -> str:
    """Case and spacing do not make a fact a different fact."""
    return " ".join(text.lower().split())


def content_id(text: str) -> str:
    """A stable id for a piece of text, so writing it twice is one record."""
    digest = hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
    return f"mem_{digest[:24]}"


def _parse_time(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def age_days(metadata: Dict[str, Any], now: Optional[datetime] = None) -> float:
    """Days since the entry was last confirmed (or, failing that, created)."""
    stamp = (
        _parse_time(metadata.get("last_verified"))
        or _parse_time(metadata.get("created"))
        or _parse_time(metadata.get("timestamp"))
    )
    if stamp is None:
        return 0.0
    return max(((now or datetime.now()) - stamp).total_seconds() / 86400.0, 0.0)


def recency(metadata: Dict[str, Any], now: Optional[datetime] = None) -> float:
    """1.0 when just confirmed, halving every HALF_LIFE_DAYS. Explicit user instructions do not
    fade."""
    if metadata.get("source") == "user":
        return 1.0
    return 0.5 ** (age_days(metadata, now) / HALF_LIFE_DAYS)


def rank_score(
    similarity: float, metadata: Dict[str, Any], now: Optional[datetime] = None
) -> float:
    confidence = float(metadata.get("confidence", DEFAULT_CONFIDENCE))
    return (
        WEIGHT_SIMILARITY * similarity
        + WEIGHT_CONFIDENCE * min(max(confidence, 0.0), 1.0)
        + WEIGHT_RECENCY * recency(metadata, now)
    )


def _clean(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma accepts only str, int, float and bool values."""
    return {k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))}


class ChromaMemoryManager:
    """
    Manages semantic memory using ChromaDB.
    Supports persistent storage on disk.
    """

    def __init__(
        self,
        persist_directory: Path,
        collection_name: str = "cortex_semantic_memory",
        embedding_model: Optional[BaseEmbeddingModel] = None,
        clear_on_init: bool = False,  # For testing or specific use cases
    ):
        if chromadb is None:
            raise ImportError(
                "Semantic memory needs ChromaDB, which is not installed. "
                "Install it with: pip install 'cortex[memory]'"
            )

        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=str(persist_directory))

        # Use provided embedding model or default to LocalEmbeddingModel
        self._embedding_model = embedding_model if embedding_model else LocalEmbeddingModel()

        # Chroma expects an embedding function, we will wrap our BaseEmbeddingModel
        class CustomEmbeddingFunction(embedding_functions.EmbeddingFunction):
            def __init__(self, embedding_model_instance: BaseEmbeddingModel):
                self._embedding_model_instance = embedding_model_instance

            def __call__(self, texts: List[str]) -> List[List[float]]:
                return self._embedding_model_instance.encode_batch(texts)

            def name(self) -> str:
                return f"cortex_{self._embedding_model_instance.__class__.__name__}"

            def get_config(self) -> Dict[str, Any]:
                return {"model_name": self._embedding_model_instance.__class__.__name__}

        self.embedding_function = CustomEmbeddingFunction(self._embedding_model)

        self.collection: Collection = self._get_or_create_collection(clear_on_init)
        logger.info(
            f"Initialized ChromaMemoryManager. "
            f"Persistence: {persist_directory}, Collection: {collection_name}, "
            f"Embedding Dimensions: {self.embedding_model.dimensions()}"
        )

    @property
    def embedding_model(self) -> BaseEmbeddingModel:
        return self._embedding_model

    def _get_or_create_collection(self, clear: bool = False) -> Collection:
        """Helper to get or create the Chroma collection."""
        try:
            if clear and self.collection_name in [
                col.name for col in self.client.list_collections()
            ]:
                logger.warning(f"Clearing existing Chroma collection: {self.collection_name}")
                self.client.delete_collection(name=self.collection_name)

            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,  # Pass the wrapped embedding function
                metadata={"hnsw:space": "cosine"},  # Explicitly use cosine similarity
            )
            return collection
        except Exception as e:
            logger.error(f"Error getting or creating Chroma collection: {e}")
            raise

    def add_document(
        self,
        text: str,
        metadata: Dict[str, Any],
        doc_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> str:
        """
        Adds a document, or re-affirms it if the same text is already stored.

        The id comes from the text (ignoring case and spacing), so writing the same fact twice
        leaves one record. The existing record keeps its creation time, counts the sighting and
        keeps the higher confidence.

        Args:
            text: The content of the document.
            metadata: A dictionary of metadata to associate with the document.
            doc_id: Optional unique ID for the document (default: derived from the text).
            now: Current time (for tests).

        Returns:
            The ID of the stored document.
        """
        if not text:
            logger.warning("Attempted to add empty text to ChromaDB. Skipping.")
            return ""  # Return empty ID for empty text

        try:
            final_id = doc_id or content_id(text)
            stamp = (now or datetime.now()).isoformat()
            merged = self._merge_metadata(self.get_document(final_id), metadata, stamp)
            self.collection.upsert(documents=[text], metadatas=[merged], ids=[final_id])
            logger.debug(f"Stored document in Chroma. ID: {final_id}")
            return final_id
        except Exception as e:
            logger.error(f"Failed to add document to Chroma: {e}")
            raise

    @staticmethod
    def _merge_metadata(
        existing: Optional[Dict[str, Any]], new: Dict[str, Any], stamp: str
    ) -> Dict[str, Any]:
        merged = _clean(dict(new))
        merged.setdefault("last_verified", stamp)
        merged["created"] = str(new.get("created") or new.get("timestamp") or stamp)
        merged["times_seen"] = 1
        if existing:
            old = existing["metadata"]
            merged["created"] = str(old.get("created") or merged["created"])
            merged["times_seen"] = int(old.get("times_seen", 1)) + 1
            merged["confidence"] = max(
                float(old.get("confidence", 0.0)), float(new.get("confidence", 0.0))
            )
            merged["last_verified"] = max(
                str(old.get("last_verified", "")), str(merged["last_verified"])
            )
        return merged

    def add_large_document(
        self, text: str, metadata: Dict[str, Any], chunk_size: int = 1000, overlap: int = 200
    ) -> List[str]:
        """
        Splits a large document into chunks and adds them to semantic memory.

        Args:
            text: Large document content
            metadata: Metadata for all chunks
            chunk_size: Maximum characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of IDs for added chunks
        """
        if not text:
            return []

        chunks = self.chunk_text(text, chunk_size, overlap)
        chunk_metadatas = []
        for i, _ in enumerate(chunks):
            chunk_md = metadata.copy()
            chunk_md["chunk_index"] = i
            chunk_md["is_chunk"] = True
            chunk_metadatas.append(chunk_md)

        return self.add_documents(chunks, chunk_metadatas)

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            # If we are near the end and the remaining text is too small to be a useful chunk
            # just take the rest and stop.
            if len(text) - start <= overlap and chunks:
                break

            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])

            if end == len(text):
                break

            start += chunk_size - overlap
        return chunks

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Adds multiple documents (each de-duplicated like add_document).

        Args:
            texts: A list of document contents.
            metadatas: A list of metadata dictionaries, corresponding to `texts`.
            ids: Optional list of unique IDs for the documents.

        Returns:
            A list of IDs for the stored documents (empty texts are skipped).
        """
        if not texts:
            return []
        if len(texts) != len(metadatas):
            raise ValueError("Lengths of texts and metadatas must match.")

        stored = []
        for i, text in enumerate(texts):
            if text:
                stored.append(
                    self.add_document(text, metadatas[i], doc_id=(ids[i] if ids else None))
                )
        if not stored:
            logger.warning("Attempted to add an empty list of valid texts to ChromaDB. Skipping.")
        return stored

    def search_documents(
        self,
        query_text: str,
        top_k: int = 5,
        where_clause: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches memory, ranking by similarity, confidence and recency together.

        Args:
            query_text: The text query to use for similarity search.
            top_k: The number of results to return.
            where_clause: Optional ChromaDB-style filter for metadata.
            session_id: Optional session ID to filter by.
            now: Current time (for tests).

        Returns:
            Dicts with 'id', 'document', 'metadata', 'distance', 'similarity' and 'score',
            best first. Ranking is computed from stored timestamps; nothing is written back.
        """
        if not query_text:
            return []

        try:
            doc_count = self.count()
            if doc_count == 0:
                return []

            # Prepare filtering
            final_where = where_clause or {}
            if session_id:
                if final_where:
                    # If there's already a where clause, combine them
                    final_where = {"$and": [final_where, {"session_id": session_id}]}
                else:
                    final_where = {"session_id": session_id}

            results = self.collection.query(
                query_texts=[query_text],
                n_results=max(1, min(top_k * CANDIDATE_FACTOR, doc_count)),
                where=final_where if final_where else None,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results["documents"] or not results["documents"][0]:
                return []

            ranked = []
            for i in range(len(results["documents"][0])):
                metadata = results["metadatas"][0][i] or {}
                distance = results["distances"][0][i]
                similarity = max(0.0, 1.0 - distance)  # cosine distance
                ranked.append(
                    {
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i],
                        "metadata": metadata,
                        "distance": distance,
                        "similarity": similarity,
                        "score": rank_score(similarity, metadata, now),
                    }
                )
            ranked.sort(key=lambda r: r["score"], reverse=True)
            logger.debug(f"Retrieved {len(ranked[:top_k])} documents for: '{query_text[:50]}...'")
            return ranked[:top_k]
        except Exception as e:
            logger.error(f"Failed to search documents in Chroma: {e}")
            return []

    # ----------------------------------------------------------------------------------
    # reading, verifying and editing individual entries
    # ----------------------------------------------------------------------------------

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """One entry as {'id', 'document', 'metadata'}, or None."""
        found = self.collection.get(ids=[doc_id], include=["documents", "metadatas"])
        if not found or not found["ids"]:
            return None
        return {
            "id": found["ids"][0],
            "document": found["documents"][0],
            "metadata": found["metadatas"][0] or {},
        }

    def list_documents(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Every entry, most recently confirmed first."""
        found = self.collection.get(include=["documents", "metadatas"])
        entries = [
            {
                "id": found["ids"][i],
                "document": found["documents"][i],
                "metadata": found["metadatas"][i] or {},
            }
            for i in range(len(found["ids"]))
        ]
        entries.sort(
            key=lambda e: str(
                e["metadata"].get("last_verified") or e["metadata"].get("created") or ""
            ),
            reverse=True,
        )
        return entries[:limit] if limit else entries

    def verify(self, doc_id: str, success: bool, now: Optional[datetime] = None) -> bool:
        """Record that something confirmed (success) or contradicted (failure) an entry.

        Confirmation raises confidence and restarts the entry's age. A contradiction lowers
        confidence but does not make the entry look fresher. Returns False for an unknown id.
        """
        record = self.get_document(doc_id)
        if record is None:
            return False
        metadata = dict(record["metadata"])
        confidence = float(metadata.get("confidence", DEFAULT_CONFIDENCE))
        if success:
            metadata["confidence"] = min(1.0, confidence + VERIFY_BOOST)
            metadata["last_verified"] = (now or datetime.now()).isoformat()
        else:
            metadata["confidence"] = max(CONFIDENCE_FLOOR, confidence - VERIFY_PENALTY)
        self.collection.update(ids=[doc_id], metadatas=[metadata])
        return True

    def verify_matching(self, substring: str, success: bool, now: Optional[datetime] = None) -> int:
        """verify() every entry whose text contains ``substring``; returns how many."""
        if not substring:
            return 0
        found = self.collection.get(where_document={"$contains": substring}, include=[])
        return sum(1 for doc_id in found["ids"] if self.verify(doc_id, success, now))

    def update_document(self, doc_id: str, new_text: str, now: Optional[datetime] = None) -> str:
        """Replace an entry's text, keeping its history. Returns the (possibly new) id.

        The id follows the text, so an edit usually changes it. If the new text already exists
        the two entries are merged into that one.
        """
        record = self.get_document(doc_id)
        if record is None:
            raise KeyError(f"No memory with id {doc_id}")
        stamp = (now or datetime.now()).isoformat()
        metadata = dict(record["metadata"])
        metadata["last_verified"] = stamp
        metadata["source"] = "user"  # a person edited it
        new_id = content_id(new_text)

        existing = self.get_document(new_id) if new_id != doc_id else None
        merged = self._merge_metadata(existing, metadata, stamp)
        if not existing:  # a fresh id: keep the history of the entry being edited
            merged["created"] = str(record["metadata"].get("created") or merged["created"])
            merged["times_seen"] = int(record["metadata"].get("times_seen", 1))
        self.collection.upsert(documents=[new_text], metadatas=[merged], ids=[new_id])
        if new_id != doc_id:
            self.delete_document(doc_id)
        return new_id

    def delete_document(self, doc_id: str) -> None:
        """Deletes a document by its ID."""
        try:
            self.collection.delete(ids=[doc_id])
            logger.debug(f"Deleted document from Chroma. ID: {doc_id}")
        except Exception as e:
            logger.error(f"Failed to delete document from Chroma: {e}")
            raise

    def count(self) -> int:
        """Returns the number of documents in the collection."""
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Failed to count documents in Chroma: {e}")
            return 0

    def clear_collection(self) -> None:
        """Clears all documents from the collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection(
                clear=False
            )  # Recreate empty collection
            logger.info(f"Chroma collection '{self.collection_name}' cleared.")
        except Exception as e:
            logger.error(f"Failed to clear Chroma collection: {e}")
            raise
