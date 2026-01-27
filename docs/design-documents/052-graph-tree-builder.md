# Design: GraphTreeBuilder

## 1. Purpose and Role

The `GraphTreeBuilder` is responsible for establishing a clean, traversable, and hierarchical structure for the project within the graph. It creates a single root `:Project` node and builds a simplified parent-child overlay of the source code's physical layout using a `[:CONTAINS_SOURCE]` relationship.

This clean hierarchy is fundamental for any analysis that needs to understand the project's structure, such as hierarchical summarization.

## 2. Passes

### Pass: `create_project_node()`

-   **What**: Creates a single, top-level `:Project` node to act as the root of the entire graph.
-   **How**:
    1.  It first auto-detects the project's root path by querying Neo4j for all `:Artifact:Directory` nodes and finding their longest common path.
    2.  It then executes a Cypher query to `MERGE` a single `:Project` node, setting its `name` and `absolute_path` properties.
    3.  Finally, it creates a `[:CONTAINS]` relationship from this `:Project` node to all existing `:Artifact` nodes, formally making them children of the project.
-   **Rationale**: This pass establishes a canonical entry point for all graph traversals and provides a logical place to store project-level metadata and summaries.

### Pass: `establish_source_hierarchy()`

-   **What**: Builds a clean parent-child tree of the source code's physical structure using a `[:CONTAINS_SOURCE]` relationship.
-   **How**: This pass intelligently builds the hierarchy from the bottom up.
    1.  It first queries for all `:Directory` nodes that have an `absolute_path` and groups them by path depth.
    2.  Iterating from the deepest level to the shallowest, it runs Cypher queries to `MERGE` `[:CONTAINS_SOURCE]` relationships from a directory to its direct children (both `:SourceFile` and other `:Directory` nodes).
    3.  Finally, it runs a separate query to link the `:Project` node to the top-level `:Directory:Artifact` nodes that are the entry points of the source tree.
-   **Rationale**: This pass creates a simplified and unambiguous structural overlay. It bypasses jQAssistant's more complex and generic `[:CONTAINS]` relationships, providing a clean tree that is ideal for hierarchical processing.

## 3. Dependencies

-   `neo4j_manager.Neo4jManager`: To execute the Cypher queries for each pass.
