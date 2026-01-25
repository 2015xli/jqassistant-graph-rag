# Designing for Modular and Scalable Summarization

This document outlines the architecture of the graph summarization engine, a system designed to be modular, scalable, efficient, and resilient. It processes a code graph in a structured, bottom-up manner to generate descriptive summaries for every node, from individual methods to the entire project.

## 1. High-Level Principles

The design is guided by a few core principles:

*   **Hierarchical, Bottom-Up Processing**: The system starts with the smallest, most fundamental code units (methods) and progressively works its way up through the hierarchy (types, files, directories, packages) to the project level. This ensures that when a parent node is being summarized, the rich context from its already-summarized children is available.
*   **Separation of Concerns**: Each component in the system has a single, well-defined responsibility. This makes the codebase easier to understand, maintain, test, and extend. For example, the logic for fetching nodes from the database is separate from the logic for generating a summary.
*   **Efficiency Through Incremental Updates**: The system is designed to be "resumable." It avoids re-processing nodes whose content or dependencies have not changed since the last run. This is crucial for large codebases where running a full analysis every time would be prohibitively slow and expensive.
*   **Resilience and Fault Tolerance**: The process can be lengthy and may be interrupted. The design ensures that progress is saved continuously and that the system can recover gracefully from failures without corrupting its state.
*   **Scalability via Token Management**: The system is designed to handle arbitrarily large contexts (e.g., methods with thousands of lines of code, classes with hundreds of members) by intelligently chunking and iteratively processing data to stay within the LLM's context window.

## 2. Key Benefits of the Design

*   **Modularity**: Adding a new summarizer for a new type of node is straightforward. It requires implementing a new specific summarizer class without altering the core processing logic.
*   **Testability**: The `NodeSummaryProcessor` encapsulates its own stateless dependencies, making it easy to unit test. Clear interfaces between components simplify integration testing.
*   **Scalability**: The combination of batch processing, incremental updates, and iterative, token-aware summarization allows the system to handle very large and complex code graphs efficiently.
*   **Maintainability**: Clear separation of concerns means that a change in one part of the system (e.g., changing a prompt or adjusting the token chunk size) has minimal impact on other parts.

## 3. Component Roles and Responsibilities

The system is composed of several key components, each with a distinct role.

### 3.1. RagOrchestrator

*   **Role**: The main entry point and conductor of the entire summarization process.
*   **Responsibilities**:
    *   Initializes the high-level components it directly interacts with: `Neo4jManager`, `LlmClient`, `EmbeddingClient`, `SummaryCacheManager`, and `NodeSummaryProcessor`.
    *   Defines the sequence of summarization passes, ensuring they run in a logical order (e.g., `MethodAnalyzer` before `MethodSummarizer`).
    *   Triggers the `run()` method of each summarizer in sequence.
    *   Manages the lifecycle of the `SummaryCacheManager`, ensuring the cache is loaded at the start and saved at the end of the run.

### 3.2. BaseSummarizer (Abstract Class)

*   **Role**: Provides the template and shared logic for all specific summarizer classes.
*   **Responsibilities**:
    *   Defines the abstract methods that concrete classes must implement.
    *   Implements the core `process_batch` method. This loop iterates over a list of nodes, sends each one to the `NodeSummaryProcessor`, collects the results, and performs a batch update to the database and the in-memory cache.

### 3.3. Specific Summarizers

*   **Role**: The data fetch and context gathering layer for a specific node type. They are responsible for providing the `NodeSummaryProcessor` with the right data in the right order.
*   **Responsibilities**:
    *   Implement a strategy to query the Neo4j database for all nodes of a specific type. The strategy depends on the node's nature:
        *   **Inheritance Hierarchy Ordering (`TypeSummarizer`)**: This is the most complex strategy. It first performs a graph traversal to map out the entire inheritance hierarchy of source-linked types, grouping them into levels. It then processes types level by level, ensuring base types are summarized before derived types.
        *   **Depth-First Ordering (`DirectorySummarizer`, `PackageSummarizer`)**: These use a single, efficient Cypher query that orders nodes by their path or FQN depth (deepest first), ensuring children are processed before parents.
        *   **Simple Fetch (All others)**: For nodes without strict hierarchical dependencies (like methods or source files), a simple query fetches all items at once.
    *   For each node, gather the element IDs of all its contextual dependencies (e.g., parents, children, callers, callees).
    *   Provide the specific Cypher query for batch-updating its node type.
    *   Call the appropriate method on the `NodeSummaryProcessor`.

### 3.4. NodeSummaryProcessor

*   **Role**: The stateless, logical core of the summarization engine. It encapsulates the "how" of summarization.
*   **Responsibilities**:
    *   Instantiates its own internal, stateless dependencies (`PromptManager`, `TokenManager`), hiding these implementation details from the orchestrator.
    *   For any given node, it decides **if** an update is needed by executing the **Decision Waterfall** logic.
    *   It orchestrates the generation of new summaries, which includes:
        *   Checking if the context is too large using the `TokenManager`.
        *   Performing single-shot summarization for small contexts.
        *   Performing **iterative, token-aware summarization** for large contexts.
    *   It contains dedicated methods for different summarization patterns (e.g., `get_method_summary`, `get_type_summary`, `get_hierarchical_summary`).

### 3.5. SummaryCacheManager

*   **Role**: The stateful persistence and change-tracking layer.
*   **Responsibilities**:
    *   Manages the on-disk JSON cache, handling loading and a resilient, multi-stage save process with backups.
    *   Maintains the `runtime_status` dictionary to track which nodes have been regenerated *during the current run*.
    *   Provides the crucial `was_dependency_changed()` method, which is the heart of the incremental update logic.

### 3.6. TokenManager

*   **Role**: A stateless utility for all token-related operations.
*   **Responsibilities**:
    *   Encapsulates the `tiktoken` library.
    *   Provides a reliable method for counting tokens in a string.
    *   Implements logic for **chunking a single large text** into smaller, overlapping segments (used for source code).
    *   Implements logic for **grouping a list of summaries** into larger chunks without splitting the individual summaries (used for context).

### 3.7. LlmClient & EmbeddingClient

*   **Role**: Simple, focused clients for communicating with external AI services.
*   **Responsibilities**:
    *   Handle the technical details of making API calls (e.g., authentication, requests, error handling).

### 3.8. PromptManager

*   **Role**: A centralized, stateless repository for all prompt engineering.
*   **Responsibilities**:
    *   Contains methods that generate the specific, formatted prompts for every scenario, including single-shot and iterative summarization.
    *   Separates the "art" of prompt writing from the application's core logic.

## 4. Low-Level Details & Workflow

### 4.1. The Decision Waterfall

For every node, the `NodeSummaryProcessor` follows a strict, three-step decision process:

1.  **Check the Database (Is the summary valid?)**: It first checks if a summary exists in Neo4j and if it is "stale." A summary is stale if `cache_manager.was_dependency_changed()` returns `True` for its dependencies. If the summary exists and is not stale, the process stops. **Result: `unchanged`**.
2.  **Check the Cache (Can the summary be restored?)**: If the database state is invalid, it checks the in-memory cache. A valid summary might exist here if it was generated in a previous pass of the *same run*. If so, it is used. **Result: `restored`**.
3.  **Regenerate (Invoke the LLM)**: If neither the database nor the cache can provide a valid summary, the processor proceeds with regeneration. **Result: `regenerated`**.

### 4.2. Token-Aware Iterative Summarization

When regeneration is required and the context exceeds the token limit, the `NodeSummaryProcessor` uses one of two iterative strategies:

1.  **Content-Based Chunking (for single texts)**: Used for a method's source code. The `TokenManager` splits the code into overlapping chunks. The processor generates a summary of the first chunk, then feeds that summary along with the next chunk into the LLM to create a refined, combined summary. This process repeats until all chunks are consumed.

2.  **Context-Based Chunking (for multiple summaries)**: Used for hierarchical nodes with many children (e.g., a class with many methods). The `TokenManager` groups the child summaries into chunks. The processor then "folds" each chunk into a running summary. For complex nodes like `:Type`, this is a multi-stage process:
    *   Start with a base summary.
    *   First, fold in all parent/inheritance summaries chunk by chunk.
    *   Second, using the result, fold in all member (method/field) summaries chunk by chunk to produce the final result.

### 4.3. End-to-End Workflow Example

Consider a change to a single source file, `user/service/UserService.java`.

1.  **RagOrchestrator Starts**: It loads the cache and begins the sequence of passes.
2.  **MethodAnalyzer**: It processes a large method in `UserService.java`. The `NodeSummaryProcessor` sees the code hash has changed. It uses the `TokenManager` to chunk the large source code and iteratively calls the LLM to produce a new `code_analysis`. The result is marked `regenerated`, and `runtime_status` is updated.
3.  **MethodSummarizer**: It processes the same method. The summary is now stale. The processor gathers the new `code_analysis` and summaries for dozens of callers and callees. The total context is too large.
    *   It starts an iterative summary with the `code_analysis`.
    *   It chunks the caller summaries and folds them into the running summary.
    *   It chunks the callee summaries and folds them into the result.
    *   The final summary is produced, and `runtime_status` is updated.
4.  **TypeSummarizer**: This pass runs in level-based order. When it gets to the `UserService` class, the `NodeSummaryProcessor` sees its method's summary has changed, marking it stale. It gathers context from parent classes and all member methods. If the context is too large, it iteratively folds in the parent context first, then the member context.
5.  **Hierarchical Passes**: The change propagates up through `SourceFileSummarizer`, `DirectorySummarizer`, and `ProjectSummarizer`. Each one uses the generic `get_hierarchical_summary` method, which will automatically trigger iterative summarization if the number of child summaries is too large.
6.  **RagOrchestrator Finishes**: The orchestrator calls `cache_manager.save()` to persist all the new content to disk.

## 5. Hierarchical Node Processing Strategies

To correctly build summaries in a bottom-up fashion, different summarizers employ distinct strategies for ordering the nodes they process. The choice of strategy is critical for ensuring that a parent node is only summarized after its constituent children have been.

### 5.1. Structural Inheritance Hierarchy (`TypeSummarizer`)

*   **Goal**: To summarize base classes and interfaces before the types that derive from them. This is the most complex and explicit form of hierarchical processing in the system.
*   **Logic**:
    1.  **Identify Scope**: First, all `:Type` nodes that are linked to source code (`-[:WITH_SOURCE]->`) are identified. This excludes types from external libraries.
    2.  **Find Level 0 (Roots)**: The summarizer finds all source-linked types that do **not** inherit from any other source-linked type. These form the top of the project's inheritance tree.
    3.  **Iterative Traversal**: The summarizer then enters a loop. In each iteration, it finds the next level of types: those whose source-linked parents have **all** been assigned to a previous level.
    4.  **Execution**: This process continues until all source-linked types have been assigned to a level. The `run` method then processes the nodes level by level, from 0 upwards.

### 5.2. Path/FQN Depth Ordering (`DirectorySummarizer`, `PackageSummarizer`)

*   **Goal**: To summarize the most deeply nested directories or packages first, moving progressively upwards.
*   **Logic**: This strategy offloads the ordering logic to the database, resulting in a very simple and efficient implementation.
    *   **`DirectorySummarizer`**: A single Cypher query fetches all `:Directory` nodes and orders them using `ORDER BY size(split(d.absolute_path, '/')) DESC`. The database returns a list of directories from the deepest to the shallowest.
    *   **`PackageSummarizer`**: A similar query fetches all `:Package` nodes and orders them using `ORDER BY size(split(p.fqn, '.')) DESC`.

### 5.3. Single Root Node (`ProjectSummarizer`)

*   **Goal**: To summarize the single `:Project` node after all other nodes have been summarized.
*   **Logic**: This is the simplest case. A direct query matches the one `:Project` node and gathers its direct children (top-level directories and packages) as context.

### 5.4. Simple Bulk Fetch (e.g., `MethodSummarizer`, `SourceFileSummarizer`)

*   **Goal**: To process a "flat" list of nodes whose summarization order does not depend on other nodes of the same type.
*   **Logic**: For these passes, a simple `MATCH (n:NodeType)` query is sufficient. The order of processing for methods (or source files) relative to each other is not important, as their primary dependencies (e.g., a source file's dependency on its types) are handled by the overall sequence of passes defined in the `RagOrchestrator`.
