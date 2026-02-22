"""
Embedding model abstraction for semantic memory.

This module defines an abstract base class for embedding models and provides
implementations for local (Sentence Transformers) and potentially cloud-based models.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseEmbeddingModel(ABC):
    """Abstract base class for all embedding models."""

    @abstractmethod
    def encode(self, text: str) -> List[float]:
        """
        Encodes a given text into a vector embedding.

        Args:
            text: The text string to encode.

        Returns:
            A list of floats representing the embedding vector.
        """
        pass

    @abstractmethod
    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Encodes a list of texts into vector embeddings.

        Args:
            texts: A list of text strings to encode.

        Returns:
            A list of lists of floats, where each inner list is an embedding vector.
        """
        pass

    @abstractmethod
    def dimensions(self) -> int:
        """
        Returns the dimensionality of the generated embeddings.

        Returns:
            An integer representing the dimension size.
        """
        pass


class LocalEmbeddingModel(BaseEmbeddingModel):
    """
    Implementation of BaseEmbeddingModel using a local Sentence Transformer model.
    Defaults to 'all-MiniLM-L6-v2' for efficient local embeddings.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            self._dimensions = self._model.get_sentence_embedding_dimension()
            logger.info(f"Initialized LocalEmbeddingModel with {model_name}, dimensions: {self._dimensions}")
        except ImportError:
            logger.error("sentence-transformers not installed. Please install it to use LocalEmbeddingModel.")
            raise
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model {model_name}: {e}")
            raise

    def encode(self, text: str) -> List[float]:
        """Encodes a single text string."""
        if not text:
            return []
        return self._model.encode(text).tolist()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encodes a batch of text strings."""
        if not texts:
            return []
        return self._model.encode(texts).tolist()

    def dimensions(self) -> int:
        """Returns the dimensionality of the embeddings."""
        return self._dimensions

# TODO: Implement OpenAIEmbeddingModel (and other cloud models) as a pluggable option
# class OpenAIEmbeddingModel(BaseEmbeddingModel):
#    ...

