# Design: GraphEntitySetter

## 1. Purpose and Role

The `GraphEntitySetter` is responsible for the final phase of graph normalization. Its sole purpose is to formally designate which nodes in the graph are considered "Entities" for the purpose of analysis and to assign them a stable, unique identifier.

This is a critical step that must happen after the graph structure is complete but before any summarization or embedding occurs, as the `entity_id` is the canonical key used for caching and all subsequent data processing.

## 2. Passes

### Pass: `create_entities_and_stable_ids()`

-   **What**: Adds an `:Entity` label to all relevant nodes and sets a unique, deterministic `entity_id` property on them.
-   **How**: This method executes a sequence of Cypher queries that target different types of nodes:
    1.  It first ensures a uniqueness constraint exists in the database for `:Entity(entity_id)` to guarantee data integrity.
    2.  It then generates the `entity_id` for the `:Project` node.
    3.  It generates `entity_id`s for `:Artifact` nodes.
    4.  It generates `entity_id`s for filesystem-like nodes (`:File`, `:Directory`, `:Package`, `:Type`) contained within an artifact.
    5.  Finally, it generates `entity_id`s for `:Member` nodes.
-   **Rationale**: The `entity_id` provides a stable, immutable identifier for each conceptual object in the codebase. This ID is essential for the summarization caching mechanism and for any external system that needs to reference a specific node in the graph. The ID is generated from a composite key (e.g., artifact path + file path + member signature) and hashed with MD5 to ensure it is unique and deterministic. This process correctly handles nodes from both filesystem and `.jar` artifacts.

## 3. Dependencies

-   `neo4j_manager.Neo4jManager`: To execute the Cypher queries.
