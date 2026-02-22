# Implementation Plan: Vector Database Integration for Semantic Memory

## 1. Objective

Integrate a vector database into Cortex to enable robust semantic memory and long-term knowledge retention. This will allow the agent to:
*   Retrieve contextually relevant information based on semantic similarity, rather than just keyword matching.
*   Overcome LLM context window limitations by efficiently storing and querying vast amounts of past interactions, codebase knowledge, and learned patterns.
*   Enhance reasoning and decision-making by providing a richer, more nuanced understanding of historical data.

## 2. Rationale

While Cortex's current layered memory (Working, Session, State) is effective for structured and short-to-medium term recall, it lacks true semantic understanding. This limits the agent's ability to:
*   Recall relevant information that isn't explicitly tagged or keyword-matched.
*   Learn and adapt over longer periods or across diverse tasks.
*   Perform complex reasoning that requires synthesizing information from a large, diffuse knowledge base.

Vector databases solve these problems by allowing us to represent information semantically and retrieve it based on meaning, significantly boosting Cortex's intelligence and effectiveness, especially in large codebases.

## 3. Technology Choice: Chroma (Initial Phase)

**Decision:** For the initial integration, we will use **Chroma DB**.

**Justification:**
*   **Local-First & Embedded:** Chroma can run entirely in-process or on disk without a separate server, aligning perfectly with Cortex's "local-first" philosophy and ease of deployment.
*   **Python Native:** Its Python client is robust and easy to use, minimizing additional language dependencies for this component.
*   **Simplicity:** Offers a straightforward API for embedding generation and similarity search, accelerating initial development.
*   **Pluggable Architecture:** The design will abstract the vector database interaction, allowing for a future transition to more scalable solutions like Qdrant or Pinecone if needed (e.g., for multi-agent or distributed memory scenarios).

**Alternative Considerations (for future phases):**
*   **Qdrant:** Excellent for production-grade, distributed, and scalable deployments with advanced filtering capabilities. Can be considered for `v2.0.0` or enterprise-focused features.
*   **Pinecone:** Managed cloud service, simplifies deployment but introduces cloud dependency.

## 4. Architectural Design

The vector database will function as a new "semantic layer" within the `cortex.core.memory` system, augmenting the existing `EnhancedMemoryBank`.

**Key Components:**

*   **`cortex.core.memory.semantic_memory.py` (New Module):**
    *   Will encapsulate the Chroma client, collection management, and CRUD operations for vector embeddings.
    *   `SemanticMemoryManager` class to handle `add_text`, `search_similar`, `delete`, etc.
*   **`cortex.core.memory.embeddings.py` (New Module):**
    *   `EmbeddingModel` interface to abstract embedding generation.
    *   Default implementation using a lightweight `sentence-transformers` model (e.g., `all-MiniLM-L6-v2`) for local-first operation.
    *   Pluggable design to allow switching to cloud-based embedding APIs (OpenAI, Cohere, etc.) via configuration.
*   **`cortex.core.memory.memory_bank.py` (Modify `EnhancedMemoryBank`):**
    *   Integrate the `SemanticMemoryManager` as a component.
    *   Modify `store_memory` to send relevant content to the vector DB.
    *   Add a new method `retrieve_semantic_context(query: str, top_k: int)` to query the vector DB.
*   **Configuration (`cortex.config.py`):**
    *   Add settings for `semantic_memory.enabled` (boolean), `semantic_memory.provider` (e.g., 'chroma'), `semantic_memory.embedding_model` (model name/API key), `semantic_memory.collection_name`.
*   **Agent Integration (`cortex.agent.py`):**
    *   Modify the agent's planning and context generation loops to incorporate semantic memory retrieval.
    *   Agent should query semantic memory *before* making decisions or generating prompts, injecting the retrieved context into the LLM's prompt.
    *   Add new command-line options or interactive prompts to manage semantic memory (e.g., `/memory embed_file <path>`, `/memory search <query>`).

## 5. Implementation Steps

### Phase 1: Core Chroma Integration & Embedding

1.  **Add Chroma Dependency:**
    *   Update `pyproject.toml`, `setup.py`, and `requirements.txt` to include `chromadb`.
    *   Add `sentence-transformers` (or a chosen local embedding model library).
2.  **`EmbeddingModel` Abstraction:**
    *   Create `cortex/core/memory/embeddings.py`.
    *   Define an `EmbeddingModel` ABC with an `encode(text: str) -> List[float]` method.
    *   Implement `SentenceTransformerEmbeddingModel` using `all-MiniLM-L6-v2`.
    *   Implement `OpenAIEmbeddingModel` (if OpenAI API key is configured).
3.  **`SemanticMemoryManager`:**
    *   Create `cortex/core/memory/semantic_memory.py`.
    *   Initialize Chroma client (persistent client for disk storage).
    *   Methods for:
        *   `add_document(text: str, metadata: Dict[str, Any], id: str = None)`: Embed text and store.
        *   `search_documents(query: str, top_k: int) -> List[Dict[str, Any]]`: Embed query, perform similarity search.
        *   `delete_document(id: str)`: Delete by ID.
        *   `get_collection_size() -> int`: Get number of documents.
        *   `clear_collection()`: Empty the collection.
4.  **Configuration:**
    *   Add relevant `semantic_memory` settings to `cortex.config.AgentConfig`.

### Phase 2: Agent Workflow Integration

1.  **Memory Bank Augmentation:**
    *   In `cortex/core/memory/memory_bank.py`, initialize `SemanticMemoryManager` based on config.
    *   Modify `store_memory` to extract relevant text (e.g., conversation turns, tool outputs, planning steps) and pass it to `SemanticMemoryManager.add_document`.
        *   *Consideration:* What granular chunks of information should be embedded? (whole messages, specific tool outputs, etc.)
    *   Implement `retrieve_semantic_context(query: str, top_k: int)` in `EnhancedMemoryBank`.
2.  **Agent Context Injection:**
    *   In `cortex/agent.py`, identify strategic points in the planning and execution loop where semantic context is needed.
    *   Before generating a new plan or executing a complex tool, query `EnhancedMemoryBank.retrieve_semantic_context` with the current goal/task.
    *   Inject the retrieved context (e.g., as a dedicated system message or within a specific prompt section) into the LLM's prompt.
3.  **CLI Commands:**
    *   Add new `cortex` CLI commands for direct interaction with semantic memory:
        *   `/memory embed <text/file>`: Manually embed and store content.
        *   `/memory search <query>`: Perform a semantic search and display results.
        *   `/memory status`: Show vector DB stats (size, document count).

### Phase 3: Refinement & Testing

1.  **Performance Benchmarking:**
    *   Measure latency of embedding generation and similarity search.
    *   Evaluate memory usage of Chroma client.
2.  **Accuracy Evaluation:**
    *   Develop test cases to assess the relevance of retrieved semantic context for various task types.
    *   Compare agent performance with and without semantic memory.
3.  **Fallback Mechanisms:**
    *   Ensure graceful fallback if embedding model or Chroma DB is unavailable or misconfigured.
4.  **Error Handling:**
    *   Implement robust error handling for all vector DB operations.
5.  **Documentation:**
    *   Update `README.md` and `docs/` with instructions on configuring and using semantic memory.

## 6. Milestones

*   **M1 (Week 1-2): Core Chroma & Embeddings**
    *   Chroma installed and basic `SemanticMemoryManager` (add/search) functional.
    *   `EmbeddingModel` interface and `SentenceTransformerEmbeddingModel` implemented.
    *   Unit tests for `SemanticMemoryManager` and `EmbeddingModel`.
*   **M2 (Week 3-4): Agent Integration & Context Injection**
    *   `EnhancedMemoryBank` modified to store/retrieve from `SemanticMemoryManager`.
    *   Agent successfully retrieves semantic context and injects it into prompts for basic tasks.
    *   CLI commands for manual embed/search.
*   **M3 (Week 5-6): Performance & Evaluation**
    *   Performance metrics collected and optimized.
    *   Accuracy evaluation of semantic retrieval.
    *   Comprehensive integration tests for the entire semantic memory workflow.
    *   Documentation updated.

## 7. Potential Challenges & Risks

*   **Embedding Model Choice:** Balancing accuracy, speed, and local-first compatibility. Large models can be slow locally.
*   **Context Chunking Strategy:** Determining the optimal size and method for breaking down content into chunks for embedding (e.g., whole files, functions, paragraphs).
*   **Retrieval Relevance:** Ensuring the `top_k` retrieved results are truly beneficial to the LLM and don't introduce noise or irrelevant information.
*   **Performance Overhead:** Embedding generation and similarity search can add latency. Need to optimize for speed.
*   **Memory Growth:** Managing the growth of the vector database on disk, especially for large codebases. Need to implement cleanup/retention policies.
*   **Platform Compatibility:** Ensuring `sentence-transformers` and Chroma run smoothly across Windows, Linux, and macOS in CI and production.
*   **Migration Path:** If we start with Chroma, designing for an easy migration to Qdrant or a distributed solution in the future.

This plan provides a structured approach to integrating semantic memory, transforming Cortex into an even more intelligent and capable agent.
