# Core Components of the jQAssistant GraphRAG Project

This document lists the primary components of the system. These components represent key areas of logic and responsibility and are candidates for more detailed, individual design documents.

## I. High-Level Orchestration

These components are the main entry points and coordinators for the major phases of the enrichment pipeline.

1.  **`GraphOrchestrator`**: Manages the initial graph pre-processing phase. Its primary responsibility is to run the sequence of components that normalize the raw jQAssistant graph into a clean and stable state, making it ready for analysis.
2.  **`RagOrchestrator`**: Manages the entire RAG (summary and embedding) generation pipeline. It defines the strict, bottom-up sequence of summarization passes and invokes the final embedding pass, ensuring that dependencies are always processed before the components that rely on them.

## II. Core Summarization Logic

This group forms the heart of the AI-driven summary generation.

3.  **`NodeSummaryProcessor`**: The central, stateless "brain" for summarization. For any given graph node, it contains the logic to decide if a new summary is needed by checking dependency freshness and content hashes. It orchestrates the call to the LLM and is responsible for handling contexts that exceed the model's limit by managing an iterative chunking and refinement process.
4.  **`BaseSummarizer`**: An abstract base class that defines a common template for all summarization passes (e.g., `TypeSummarizer`, `DirectorySummarizer`). It encapsulates the shared logic for querying items, processing them in a parallel thread pool, handling results, and writing the updates back to the database in a batch.
5.  **`PackageSummarizer`**: A hierarchical summarizer that operates on the `[:CONTAINS_CLASS]` hierarchy. It generates summaries for validated package structures, starting from the deepest packages and rolling up to the `:ClassTree` roots (e.g., JAR files).
6.  **`SummaryCacheManager`**: Manages the on-disk JSON cache (`.cache/summary_cache.json`). This component is critical for the system's efficiency and correctness. It persists generated summaries and content hashes between runs and tracks the runtime status of nodes to determine if dependencies are "stale."

## III. Key Enrichment & Normalization Components

These components are responsible for specific, high-impact transformations of the graph structure. They are executed in a precise order by the `GraphOrchestrator`.

7.  **`GraphBasicNormalizer`**: Executes the first, foundational passes. It adds a canonical `absolute_path` to all filesystem nodes and applies the `:SourceFile` label to all relevant source code files.
8.  **`SourceFileLinker`**: Bridges the gap between the logical graph and physical source code. It queries the graph for `:SourceFile` nodes, parses them using `tree-sitter`, and creates `[:WITH_SOURCE]` relationships from `:Type` and `:Member` nodes to their source.
9.  **`GraphTreeBuilder`**: Establishes the project's hierarchical structure. It creates the root `:Project` node and builds a clean `[:CONTAINS_SOURCE]` tree overlay, representing the physical layout of the source code.
10. **`ArtifactDataNormalizer`**: A new, critical component that corrects the core graph structure. It relocates misplaced `:Artifact` labels to the true roots of class hierarchies, rewrites the `[:CONTAINS]` relationships to be consistent, and then builds the clean `[:CONTAINS_CLASS]` hierarchy overlay.
11. **`GraphEntitySetter`**: Executes the final normalization pass. It applies the `:Entity` label to all nodes relevant for analysis and generates a stable, unique `entity_id` for each, which is critical for caching.
12. **Source Parsers (`JavaSourceParser`, `KotlinSourceParser`)**: These components are critical for extracting metadata from raw source code files. They use `tree-sitter` to parse Java and Kotlin files, identifying package names and Fully Qualified Names (FQNs) of top-level types. This information is then used by the `SourceFileLinker` to establish connections between graph nodes and their corresponding source files.
13. **`EntityEmbedder`**: The final component in the RAG pipeline. It is responsible for generating vector embeddings from the final, high-quality summaries. It then stores these embeddings in the graph and ensures a vector index exists in Neo4j, enabling semantic search capabilities.

## IV. Foundational Utilities

These are critical support components that encapsulate complex or recurring logic.

14. **`TokenManager`**: A crucial utility that encapsulates the logic for managing the LLM's context window limitations. It provides methods for counting tokens and, most importantly, for chunking large pieces of text or lists of summaries into appropriately sized pieces for iterative processing.
