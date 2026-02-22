import time
import statistics
from pathlib import Path
import shutil
from cortex.core.memory.semantic import ChromaMemoryManager
from cortex.core.memory.embeddings import LocalEmbeddingModel

def benchmark():
    test_dir = Path("./tmp_benchmark_db")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    
    print("\n--- 1. Initialization Benchmark ---")
    start = time.perf_counter()
    model = LocalEmbeddingModel()
    init_time = time.perf_counter() - start
    print(f"Embedding Model Init: {init_time:.4f}s")

    manager = ChromaMemoryManager(persist_directory=test_dir, clear_on_init=True)
    
    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "System architecture involves many layers of abstraction.",
        "Debugging is the process of finding and resolving bugs.",
        "Artificial intelligence is transforming software engineering.",
        "Semantic memory allows agents to recall relevant history."
    ]
    
    print("\n--- 2. Indexing Latency ---")
    latencies = []
    for text in texts:
        start = time.perf_counter()
        manager.add_document(text, {"metadata": "test"})
        latencies.append(time.perf_counter() - start)
    
    print(f"Avg Indexing Latency: {statistics.mean(latencies):.4f}s")
    print(f"Max Indexing Latency: {max(latencies):.4f}s")

    print("\n--- 3. Search Latency (100 documents) ---")
    # Fill up to 100 documents
    filler_texts = [f"Random filler text for document {i}" for i in range(95)]
    filler_metadatas = [{"index": i} for i in range(95)]
    manager.add_documents(filler_texts, filler_metadatas)
    
    queries = ["fox", "software engineering", "memory", "layers", "abstraction"]
    search_latencies = []
    for q in queries:
        start = time.perf_counter()
        results = manager.search_documents(q, top_k=3)
        search_latencies.append(time.perf_counter() - start)
    
    print(f"Avg Search Latency: {statistics.mean(search_latencies):.4f}s")
    
    # Cleanup
    if test_dir.exists():
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    benchmark()
