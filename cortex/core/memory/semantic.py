"""
Semantic Memory Manager using ChromaDB for vector storage and retrieval.

This module provides an interface for storing and querying text embeddings,
acting as a long-term semantic memory for the Cortex agent.
"""

import logging
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

from .embeddings import BaseEmbeddingModel, LocalEmbeddingModel # Assuming LocalEmbeddingModel is the default

logger = logging.getLogger(__name__)


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
        clear_on_init: bool = False, # For testing or specific use cases
    ):
        if chromadb is None:
            raise ImportError(
                "ChromaDB is not installed. Please install it with 'pip install chromadb'."
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
            if clear and self.collection_name in [col.name for col in self.client.list_collections()]:
                logger.warning(f"Clearing existing Chroma collection: {self.collection_name}")
                self.client.delete_collection(name=self.collection_name)
            
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function, # Pass the wrapped embedding function
                metadata={"hnsw:space": "cosine"} # Explicitly use cosine similarity
            )
            return collection
        except Exception as e:
            logger.error(f"Error getting or creating Chroma collection: {e}")
            raise

    def add_document(self, text: str, metadata: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        """
        Adds a single document to the semantic memory.

        Args:
            text: The content of the document.
            metadata: A dictionary of metadata to associate with the document.
            doc_id: Optional unique ID for the document. If None, Chroma generates one.

        Returns:
            The ID of the added document.
        """
        if not text:
            logger.warning("Attempted to add empty text to ChromaDB. Skipping.")
            return "" # Return empty ID for empty text

        import uuid
        try:
            # ChromaDB handles embedding internally with the provided embedding_function
            # Use UUID for more reliable IDs
            final_id = doc_id or f"doc_{uuid.uuid4()}"
            
            self.collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[final_id]
            )
            logger.debug(f"Added document to Chroma. ID: {final_id}")
            return final_id
        except Exception as e:
            logger.error(f"Failed to add document to Chroma: {e}")
            raise

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

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """
        Adds multiple documents to the semantic memory.

        Args:
            texts: A list of document contents.
            metadatas: A list of metadata dictionaries, corresponding to `texts`.
            ids: Optional list of unique IDs for the documents.

        Returns:
            A list of IDs for the added documents.
        """
        if not texts:
            return []
        if len(texts) != len(metadatas):
            raise ValueError("Lengths of texts and metadatas must match.")
        
        import uuid
        # Filter out empty texts and their corresponding metadatas/ids
        filtered_texts, filtered_metadatas, filtered_ids = [], [], []
        for i, text in enumerate(texts):
            if text:
                filtered_texts.append(text)
                filtered_metadatas.append(metadatas[i])
                if ids and ids[i]:
                    filtered_ids.append(ids[i])
                else:
                    # Generate a unique ID if not provided
                    filtered_ids.append(f"doc_{uuid.uuid4()}")

        if not filtered_texts:
            logger.warning("Attempted to add an empty list of valid texts to ChromaDB. Skipping.")
            return []

        try:
            self.collection.add(
                documents=filtered_texts,
                metadatas=filtered_metadatas,
                ids=filtered_ids
            )
            logger.debug(f"Added {len(filtered_texts)} documents to Chroma.")
            return filtered_ids
        except Exception as e:
            logger.error(f"Failed to add documents to Chroma: {e}")
            raise

    def search_documents(
        self,
        query_text: str,
        top_k: int = 5,
        where_clause: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches for semantically similar documents in the memory.

        Args:
            query_text: The text query to use for similarity search.
            top_k: The number of top similar documents to retrieve.
            where_clause: Optional ChromaDB-style filter for metadata.
            session_id: Optional session ID to filter by.

        Returns:
            A list of dictionaries, each containing 'document', 'metadata', and 'distance'.
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
                n_results=top_k,
                where=final_where if final_where else None,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results['documents'] or not results['documents'][0]:
                return []

            formatted_results = []
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
            logger.debug(f"Retrieved {len(formatted_results)} documents from Chroma for query: '{query_text[:50]}...'")
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search documents in Chroma: {e}")
            # Consider returning empty list or re-raising based on desired fallback
            return []

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
            self.collection = self._get_or_create_collection(clear=False) # Recreate empty collection
            logger.info(f"Chroma collection '{self.collection_name}' cleared.")
        except Exception as e:
            logger.error(f"Failed to clear Chroma collection: {e}")
            raise

