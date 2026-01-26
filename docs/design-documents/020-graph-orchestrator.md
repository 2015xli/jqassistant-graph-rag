# Design: GraphOrchestrator

## 1. Purpose and Role

The `GraphOrchestrator` is a high-level coordinator responsible for managing the initial graph normalization and enrichment phase. Its primary role is to transform the raw, structural graph produced by jQAssistant into a clean, stable, and analyzable state. It acts as the entry point for all pre-processing activities that must occur before the RAG (summarization and embedding) pipeline can run.

## 2. Workflow

The orchestrator follows a simple, sequential workflow to prepare the graph:

1.  **Initialization**: Upon creation, it receives an active `Neo4jManager` instance.
2.  **Project Root Detection**: Its first and most critical task is to automatically determine the project's root directory. It does this by querying the graph for all `:Artifact:Directory` nodes and finding their longest common file system path. This calculated path becomes the ground truth for resolving all relative paths into absolute paths later in the process.
3.  **Source Code Linking**: It instantiates and runs the `SourceFileLinker`. This component parses the project's source code (`.java`, `.kt`) and creates `[:WITH_SOURCE]` relationships in the graph, linking logical `:Type` nodes (from bytecode) to the physical `:SourceFile` nodes that define them.
4.  **Graph Normalization**: It instantiates and runs the `GraphNormalizer`, which executes a series of essential transformation passes to clean up the graph structure, add stable identifiers, and create a clear hierarchy for analysis.

## 3. Key Methods

-   `__init__(self, neo4j_manager: Neo4jManager)`: The constructor requires an active `Neo4jManager` to interact with the database.
-   `_determine_project_root() -> Path`: A private method that contains the logic for auto-detecting the project's root path. It fetches all directory-based artifact paths from Neo4j and uses `os.path.commonpath` to find the common base. This is crucial for ensuring all subsequent file operations are based on a consistent root.
-   `run_enrichment_passes()`: This is the main public method. It orchestrates the instantiation and execution of the `SourceFileLinker` and `GraphNormalizer` in the correct order.

## 4. Dependencies

The `GraphOrchestrator` depends on the following components:

-   `neo4j_manager.Neo4jManager`: To execute Cypher queries for determining the project root.
-   `source_file_linker.SourceFileLinker`: To perform the source code linking pass.
-   `graph_normalizer.GraphNormalizer`: To execute all graph normalization passes.

## 5. Design Rationale

The `GraphOrchestrator` is designed as a high-level "director" or "facade" for the complex pre-processing phase. This design offers several advantages:

-   **Separation of Concerns**: It separates the concern of *what* pre-processing steps to run and in *what order* from the implementation details of *how* each step is performed. The main `main.py` script only needs to interact with this single orchestrator, not with the individual `GraphNormalizer` or `SourceFileLinker` components.
-   **Centralized Control**: It provides a single point of control for the entire graph enrichment workflow, making the process easier to understand, manage, and modify.
-   **State Management**: By determining and holding the `project_path`, it provides this critical piece of state to all subsequent components that need it.
