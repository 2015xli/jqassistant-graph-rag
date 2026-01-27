# Design: GraphNormalizer

## 1. Purpose and Role

The `GraphNormalizer` is a foundational component responsible for transforming the raw, often ambiguous graph produced by jQAssistant into a clean, stable, and predictable structure. It executes a series of non-destructive enrichment passes that add new properties, labels, and relationships to the graph. This "normalized" structure is a prerequisite for all subsequent analysis and summarization, as it provides the clear, unambiguous identifiers and hierarchies that the rest of the system relies on.

## 2. Workflow and Normalization Passes

The `GraphNormalizer`'s main public method, `run_all_passes()`, executes a sequence of distinct normalization passes in a specific order. Each pass is implemented as a private method that runs one or more Cypher queries.

1.  **`_create_project_node()`**: Creates a single, top-level `:Project` node. This node serves as a unified root for the entire analysis, simplifying queries that need a single entry point into the graph. It sets the project's `name` and `absolute_path`.
2.  **`_identify_and_label_entry_nodes()`**: Finds the `:Artifact:Directory` nodes that represent the top-level scanned directories, labels them as `:Entry`, and connects them to the `:Project` node. This formally establishes the main entry points of the codebase within the graph.
3.  **`_add_absolute_path_to_filesystem_nodes()`**: This pass is crucial for resolving path ambiguity. It iterates through all `:File` and `:Directory` nodes within an `:Entry` artifact and calculates a canonical `absolute_path` property for them by concatenating the artifact's `fileName` (which is an absolute path) with the node's own `fileName` (which is a relative path).
4.  **`_label_source_files()`**: Identifies all `:File` nodes whose `absolute_path` ends in `.java` or `.kt` and adds the `:SourceFile` label to them. This clearly distinguishes source code files from other file types (like `.class` files or resources).
5.  **`_identify_entities()`**: This is a critical pass that creates a stable, unique `entity_id` for every node relevant to the RAG process and labels them as `:Entity`. This pass is executed *before* establishing the direct source hierarchy and linking members, as the `entity_id` is used for matching and tracking in subsequent passes.
    *   It first ensures a uniqueness constraint exists on `:Entity(entity_id)`.
    *   It then generates the `entity_id` for different node types using a composite key that guarantees uniqueness (e.g., for a `:Type`, the key is the combination of its containing artifact's path and its own internal path). This `entity_id` becomes the canonical identifier used for all caching and dependency tracking.
6.  **`_establish_direct_source_hierarchy()`**: Creates a clean, direct parent-child hierarchy for the source code structure using `[:CONTAINS_SOURCE]` relationships. This pass now processes directories level by level, from the deepest to the shallowest. For each level, it first links directories to their direct `:SourceFile` children and then links directories to their direct `:Directory` children. This level-by-level approach ensures that all child relationships are established before a parent attempts to link to them, preventing inconsistencies and providing a robust tree structure for hierarchical summarization.
7.  **`_link_members_to_source_files()`**: After types are linked to source files (by the `SourceFileLinker`), this pass creates a direct `[:WITH_SOURCE]` link from `:Method` and `:Field` nodes to their containing `:SourceFile`. This provides a convenient shortcut for finding the source code of a specific member.

## 3. Key Methods

-   `run_all_passes()`: The main public method that executes the entire sequence of normalization passes.
-   Each private method (`_create_project_node`, `_add_absolute_path_to_filesystem_nodes`, etc.) corresponds to a single, focused normalization pass and contains the specific Cypher queries to perform the transformation.

## 4. Dependencies

-   `neo4j_manager.Neo4jManager`: Used extensively to execute the Cypher queries for each pass.

## 5. Design Rationale

-   **Idempotency**: The normalization passes are designed to be idempotent. Thanks to the use of `MERGE` and `CREATE...IF NOT EXISTS`, they can be run multiple times on the same graph without causing errors or creating duplicate data. This makes the process robust and re-runnable.
-   **Unambiguous Foundation**: The core purpose of this component is to build a solid foundation for the rest of the application. The raw jQAssistant graph contains ambiguities (e.g., `fileName` meaning different things in different contexts, no stable IDs). The `GraphNormalizer` resolves these ambiguities by adding canonical properties like `absolute_path` and `entity_id`, which are essential for the correctness of caching, summarization, and analysis.
-   **Separation of Concerns**: It cleanly separates the concern of "cleaning the graph" from the concern of "analyzing the graph." The RAG components can operate on the assumption that they are dealing with a clean, predictable structure, because the `GraphNormalizer` has already guaranteed it.
-   **Modularity**: Each normalization pass is a self-contained method. This makes it easy to understand, test, and modify individual passes or change their execution order if needed.
