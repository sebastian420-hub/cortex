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

## 5. Implementation Steps (Completed)

### Phase 1: Core Chroma Integration & Embedding (Status: DONE)

1.  **Chroma Dependency:** Added `chromadb` and `sentence-transformers` to dependencies.
2.  **`EmbeddingModel` Abstraction:** Implemented in `cortex/core/memory/embeddings.py` using `all-MiniLM-L6-v2`.
3.  **`SemanticMemoryManager`:** Implemented as `ChromaMemoryManager` in `cortex/core/memory/semantic.py`. Supports persistent disk storage and UUID-based document IDs.
4.  **Configuration:** Added `semantic_memory` settings to `AgentConfig` in `cortex/config.py`.

### Phase 2: Agent Workflow Integration (Status: DONE)

1.  **Memory Bank Augmentation:** `EnhancedMemoryBank` in `cortex/core/memory_layers/session.py` now integrates `ChromaMemoryManager`. 
2.  **Automatic Indexing:** `add()`, `add_fact()`, `add_decision()`, and `add_preference()` now automatically index items semantically.
3.  **Context Retrieval:** `retrieve_semantic_context()` retrieves top-K similar memories.
4.  **Agent Context Injection:** `Cortex._get_system_prompt()` in `cortex/agent.py` retrieves context based on the last user message and injects it into the prompt via `PromptBuilder`.
5.  **CLI Commands:** Enhanced `/memory` command with `search <query>` and status subcommands in `cortex/cli_commands/commands/memory.py`.

### Phase 3: Refinement & Evaluation (Status: DONE)

1.  **Performance Benchmarking:** Verified local-first latency (Indexing ~40ms, Search ~15ms).
2.  **Robust Error Handling:** Added try-except blocks across the memory stack to ensure graceful degradation if ChromaDB fails.
3.  **Chunking Strategy:** Implemented `add_large_document` with overlapping chunks (1000 chars, 200 overlap) for items > 1500 characters.
4.  **Verification:** Created end-to-end integration tests in `tests/integration/test_semantic_memory_flow.py`.

## 6. Performance Baseline (Local Machine)

*   **Model Initialization:** ~9.0s (one-time load of SentenceTransformer)
*   **Indexing Latency:** ~42ms per document
*   **Search Latency:** ~13ms (100 document collection)
*   **Storage Overhead:** Minimal (persisted in `.cortex/semantic_db`)

## 7. Future Considerations

*   **Quantization:** Use quantized embedding models to reduce initialization time and memory footprint.
*   **Hybrid Search:** Combine keyword matching with semantic retrieval for better precision in technical contexts.
*   **Cleanup Policies:** Implement TTL (Time-To-Live) for older semantic memories to manage growth.
*   **Scalability:** Investigate Qdrant for multi-agent or cloud-native deployments.

This plan provides a structured approach to integrating semantic memory, transforming Cortex into an even more intelligent and capable agent.
