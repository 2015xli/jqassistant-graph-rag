# 010: Implement Entity Identification Pass

This document details the plan for creating a new normalization pass in the `GraphNormalizer` to generate and apply the `entity_id` and `:Entity` label.

## 1. New Public Method in `GraphNormalizer`

A new public method, `identify_entities()`, will be added to the `GraphNormalizer` class. This method will serve as the entry point for this pass and will orchestrate all the necessary Cypher queries.

## 2. Database Constraint

The very first step within `identify_entities()` will be to ensure data integrity by creating a uniqueness constraint on the `entity_id` property for the `:Entity` label.

*   **Cypher**: `CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE`

## 3. `entity_id` Generation Logic

The method will execute a sequence of Cypher queries to generate the `entity_id` for different node types. The ID will be the MD5 hash of a unique string. The `apoc.util.md5()` function will be used for hashing.

### 3.1. For `:Project` Nodes

*   **Unique String**: The project's `name`.
*   **Cypher**:
    ```cypher
    MATCH (p:Project)
    SET p:Entity, p.entity_id = apoc.util.md5([p.name])
    ```

### 3.2. For `:Artifact` Nodes

*   **Unique String**: The artifact's `fileName` (its absolute path).
*   **Cypher**:
    ```cypher
    MATCH (a:Artifact)
    WHERE a.fileName IS NOT NULL
    SET a:Entity, a.entity_id = apoc.util.md5([a.fileName])
    ```

### 3.3. For File-System-Like Nodes (`:File`, `:Directory`, `:Package`, `:Type`)

These nodes are uniquely identified by their own `fileName` in combination with the `fileName` of the `:Artifact` that contains them.

*   **Unique String**: `"{Artifact.fileName}::{Node.fileName}"`
*   **Cypher**:
    ```cypher
    MATCH (a:Artifact)-[:CONTAINS*0..]->(n)
    WHERE (n:File OR n:Directory OR n:Package OR n:Type) AND n.fileName IS NOT NULL
    SET n:Entity, n.entity_id = apoc.util.md5([a.fileName, n.fileName])
    ```

### 3.4. For `:Member` Nodes (`:Method`, `:Field`)

Members are uniquely identified by their `signature` within the scope of their parent `:Type`, which is in turn scoped by its containing `:Artifact`.

*   **Unique String**: `"{Artifact.fileName}::{Type.fileName}::{Member.signature}"`
*   **Cypher**:
    ```cypher
    MATCH (a:Artifact)-[:CONTAINS*0..]->(t:Type)-[:DECLARES]->(m:Member)
    WHERE t.fileName IS NOT NULL AND m.signature IS NOT NULL
    SET m:Entity, m.entity_id = apoc.util.md5([a.fileName, t.fileName, m.signature])
    ```

By executing these queries in sequence, we will establish a stable and unique `entity_id` for every node that is relevant to the summarization process.
