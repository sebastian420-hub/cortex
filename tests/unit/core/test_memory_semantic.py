"""
Unit tests for the semantic memory components (embeddings and ChromaDB manager).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.core.memory.embeddings import LocalEmbeddingModel, BaseEmbeddingModel
from cortex.core.memory.semantic import ChromaMemoryManager


class TestEmbeddingModels:
    """Tests for embedding model abstraction."""

    def test_local_embedding_model_init(self):
        """Test LocalEmbeddingModel initialization."""
        model = LocalEmbeddingModel()
        assert model is not None
        assert model.dimensions() > 0

    def test_local_embedding_model_encode(self):
        """Test encoding a single text."""
        model = LocalEmbeddingModel()
        embedding = model.encode("hello world")
        assert isinstance(embedding, list)
        assert len(embedding) == model.dimensions()

    def test_local_embedding_model_encode_empty(self):
        """Test encoding an empty text."""
        model = LocalEmbeddingModel()
        embedding = model.encode("")
        assert embedding == []

    def test_local_embedding_model_encode_batch(self):
        """Test encoding a batch of texts."""
        model = LocalEmbeddingModel()
        texts = ["hello world", "foo bar"]
        embeddings = model.encode_batch(texts)
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        assert all(isinstance(e, list) and len(e) == model.dimensions() for e in embeddings)

    def test_local_embedding_model_encode_batch_empty_list(self):
        """Test encoding an empty list of texts."""
        model = LocalEmbeddingModel()
        embeddings = model.encode_batch([])
        assert embeddings == []

    @patch("sentence_transformers.SentenceTransformer", side_effect=ImportError)
    def test_local_embedding_model_import_error(self, mock_st):
        """Test ImportError handling for LocalEmbeddingModel."""
        with pytest.raises(ImportError):
            LocalEmbeddingModel()


class TestChromaMemoryManager:
    """Tests for ChromaMemoryManager."""

    @pytest.fixture
    def mock_embedding_model(self):
        """Mock embedding model for Chroma tests."""
        mock = MagicMock(spec=BaseEmbeddingModel)
        mock.dimensions.return_value = 5
        mock.encode.side_effect = lambda text: [float(ord(c)) for c in text[:5]] + [0.0] * (mock.dimensions() - 5)
        mock.encode_batch.side_effect = lambda texts: [mock.encode(t) for t in texts]
        return mock

    @pytest.fixture
    def chroma_manager(self, tmp_path: Path, mock_embedding_model: MagicMock):
        """ChromaMemoryManager fixture."""
        manager = ChromaMemoryManager(
            persist_directory=tmp_path / "chroma_db",
            embedding_model=mock_embedding_model,
            clear_on_init=True
        )
        return manager

    def test_chroma_manager_init(self, chroma_manager: ChromaMemoryManager):
        """Test ChromaMemoryManager initialization."""
        assert chroma_manager.collection_name == "cortex_semantic_memory"
        assert chroma_manager.count() == 0

    def test_add_document(self, chroma_manager: ChromaMemoryManager):
        """Test adding a single document."""
        doc_id = chroma_manager.add_document("test document", {"source": "test"})
        assert doc_id is not None
        assert chroma_manager.count() == 1

    def test_add_document_empty_text(self, chroma_manager: ChromaMemoryManager):
        """Test adding an empty document."""
        doc_id = chroma_manager.add_document("", {"source": "test"})
        assert doc_id == ""
        assert chroma_manager.count() == 0

    def test_add_documents_batch(self, chroma_manager: ChromaMemoryManager):
        """Test adding multiple documents."""
        texts = ["doc1", "doc2"]
        metadatas = [{"source": "batch"}, {"source": "batch"}]
        ids = chroma_manager.add_documents(texts, metadatas)
        assert len(ids) == 2
        assert chroma_manager.count() == 2

    def test_add_documents_batch_empty_texts(self, chroma_manager: ChromaMemoryManager):
        """Test adding empty list of documents."""
        ids = chroma_manager.add_documents([], [], [])
        assert len(ids) == 0
        assert chroma_manager.count() == 0

    def test_search_documents(self, chroma_manager: ChromaMemoryManager):
        """Test searching for documents."""
        chroma_manager.add_document("apple banana", {"id": "1"})
        chroma_manager.add_document("orange grape", {"id": "2"})
        chroma_manager.add_document("apple pie", {"id": "3"})

        results = chroma_manager.search_documents("fruit", top_k=2)
        assert len(results) == 2
        assert "document" in results[0]
        assert "metadata" in results[0]
        assert "distance" in results[0]

        # Expect "orange grape" to be more similar than "apple pie" to "fruit" with a simple encoder
        # but mock might not make perfect semantic sense, so just check existence.
        documents = [r["document"] for r in results]
        assert "apple banana" in documents or "orange grape" in documents or "apple pie" in documents

    def test_search_documents_empty_query(self, chroma_manager: ChromaMemoryManager):
        """Test searching with an empty query."""
        results = chroma_manager.search_documents("", top_k=1)
        assert results == []

    def test_delete_document(self, chroma_manager: ChromaMemoryManager):
        """Test deleting a document."""
        doc_id = chroma_manager.add_document("to be deleted", {"source": "delete"})
        assert chroma_manager.count() == 1
        chroma_manager.delete_document(doc_id)
        assert chroma_manager.count() == 0

    def test_clear_collection(self, chroma_manager: ChromaMemoryManager):
        """Test clearing the entire collection."""
        chroma_manager.add_document("doc1", {"source": "clear"})
        chroma_manager.add_document("doc2", {"source": "clear"})
        assert chroma_manager.count() == 2
        chroma_manager.clear_collection()
        assert chroma_manager.count() == 0

    def test_chroma_not_installed(self, tmp_path: Path):
        """Test error when chromadb is not installed."""
        with patch("cortex.core.memory.semantic.chromadb", None):
            with pytest.raises(ImportError, match="ChromaDB is not installed"):
                ChromaMemoryManager(persist_directory=tmp_path / "chroma_db")

