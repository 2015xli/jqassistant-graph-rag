# Design: RagOrchestrator

## 1. Purpose and Role

The `RagOrchestrator` is the high-level coordinator for the entire RAG (Retrieval-Augmented Generation) content creation pipeline. Its primary responsibility is to manage the complex process of generating AI summaries and vector embeddings for the normalized graph. It ensures that all summarization and embedding passes are executed in the correct, dependency-first order.

## 2. Workflow

The `RagOrchestrator` follows a precise, multi-stage workflow:

1.  **Initialization**: The constructor is responsible for a significant amount of setup. It instantiates and wires together all the components required for the RAG pipeline, including the `LlmClient`, `EmbeddingClient`, `SummaryCacheManager`, `NodeSummaryProcessor`, and all the individual `Summarizer` and `Embedder` classes.
2.  **Cache Loading**: The main `run_rag_passes()` method begins by loading the on-disk summary cache into memory via the `SummaryCacheManager`. This makes historical data available to the current run, preventing redundant work.
3.  **Summarization Sequence**: The orchestrator then executes a series of summarization passes in a hardcoded, bottom-up sequence. This order is critical to the system's correctness, as it ensures that summaries for constituent parts (e.g., methods) are available before the components that contain them (e.g., classes) are summarized. The sequence is:
    1.  `MethodAnalyzer`
    2.  `MethodSummarizer`
    3.  `TypeSummarizer`
    4.  `SourceFileSummarizer`
    5.  `DirectorySummarizer`
    6.  `ProjectSummarizer`
4.  **Embedding Pass**: After all summaries have been generated and updated in the graph, it invokes the `EntityEmbedder` to generate vector embeddings for all summarized entities and create the necessary vector index in Neo4j.
5.  **Cache Persistence**: The entire workflow within `run_rag_passes()` is wrapped in a `try...finally` block. The `finally` block guarantees that `self.cache_manager.save()` is called, ensuring that the (potentially updated) in-memory cache is safely written back to disk, even if an error occurs during one of the passes.

## 3. Key Methods

-   `__init__(self, neo4j_manager, project_path, llm_api)`: A heavy constructor that acts as a dependency injection point. It initializes the entire object graph of components needed for the RAG process.
-   `run_rag_passes()`: The main public entry point that executes the complete, ordered sequence of RAG generation tasks.

## 4. Dependencies

The `RagOrchestrator` is a major hub, depending on nearly all other components in the system:
-   `neo4j_manager.Neo4jManager`
-   `llm_client.LlmClient` and `llm_client.EmbeddingClient`
-   `summary_cache_manager.SummaryCacheManager`
-   `node_summary_processor.NodeSummaryProcessor`
-   All `Summarizer` classes (e.g., `MethodSummarizer`, `TypeSummarizer`, etc.)
-   `entity_embedder.EntityEmbedder`

## 5. Design Rationale

-   **Centralized Pipeline Definition**: The `RagOrchestrator` centralizes the complex setup and execution logic of the RAG pipeline. The strict, hardcoded sequence of passes is a key design decision to enforce the bottom-up data dependency flow, which is fundamental to generating high-quality, contextual summaries.
-   **Robustness**: The use of a `try...finally` block to save the cache is a critical design choice for robustness. It prevents the loss of valuable (and expensive) LLM-generated data in the event of a runtime error in one of the later passes.
-   **Separation of Concerns**: Like the `GraphOrchestrator`, it separates the high-level concern of *what* to run and in *what order* from the low-level implementation details of each pass. The main application entry point only needs to create and run this single orchestrator for the entire RAG process.
