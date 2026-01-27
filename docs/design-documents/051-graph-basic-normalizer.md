# Design: GraphBasicNormalizer

## 1. Purpose and Role

The `GraphBasicNormalizer` is responsible for the first, most fundamental phase of graph normalization. It performs low-level cleanup to resolve path ambiguities and explicitly identify source code files.

The passes in this component are prerequisites for almost all other processing. By creating a canonical `absolute_path` for every filesystem node and labeling source files, it provides a stable foundation for subsequent components like the `SourceFileLinker` and `GraphTreeBuilder` to operate on.

## 2. Passes

### Pass: `add_absolute_paths()`

-   **What**: Adds a canonical `absolute_path` property to all `:File` and `:Directory` nodes that exist on the filesystem.
-   **How**: This method runs two Cypher queries in sequence:
    1.  It first finds all `:Artifact:Directory` nodes and sets their `absolute_path` property to be the same as their `fileName` property.
    2.  It then finds all `:File` and `:Directory` nodes contained within those artifacts and sets their `absolute_path` by concatenating the artifact's `fileName` with the node's own `fileName` (which is relative).
-   **Rationale**: This is a critical pass that resolves the ambiguity of jQAssistant's `fileName` property. The `absolute_path` becomes the single, unambiguous identifier for a node's location on disk, essential for parsing and hierarchy building.

### Pass: `label_source_files()`

-   **What**: Identifies `:File` nodes that represent source code and adds a `:SourceFile` label to them.
-   **How**: It executes a Cypher query that finds all `:File` nodes whose `absolute_path` ends with `.java` or `.kt`.
-   **Rationale**: This pass explicitly marks the files that need to be parsed, allowing the `SourceFileLinker` to query for them directly instead of scanning the entire filesystem. It depends on the `absolute_path` property being present.

## 3. Dependencies

-   `neo4j_manager.Neo4jManager`: To execute the Cypher queries for each pass.
