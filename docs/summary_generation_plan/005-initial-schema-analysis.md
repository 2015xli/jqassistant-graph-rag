# Plan: 005 - Initial Schema Analysis

## 1. Goal

The primary goal of this initial pass is to thoroughly understand the existing jQAssistant-generated Neo4j graph schema. This involves identifying key node labels, their properties, and the relationships between them, specifically focusing on how files, directories, packages, and types (classes, interfaces, enums, annotations, records, modules) are represented. This understanding is crucial for designing the subsequent enrichment and summarization passes.

## 2. Key Questions to Answer

*   What are the common labels for files, directories, packages, various types (Class, Interface, Enum, Annotation, Record, Module), and artifacts (Jar)?
*   What properties do these nodes have? (e.g., `fileName`, `fqn`, `name`, `id`).
*   How are files and directories related? (e.g., `[:CONTAINS]`). Is it transitive?
*   How are types related to files? (e.g., `[:DECLARES]`, `[:CONTAINS]`).
*   How are types related to packages? (jQAssistant uses `[:CONTAINS]` for `Class`-`Package` relationships).
*   How are methods related to types? (e.g., `[:DECLARES]`, `[:CONTAINS]`).
*   What relationship type does jQAssistant use for method calls? (It uses `[:INVOKES]`, not `[:CALLS]`).
*   How are `Artifact` (Jar) nodes related to packages and other entities?
*   What are the unique identifiers for each node type? (e.g., `fileName` for files/directories, `fqn` for types, `name` for artifacts).

## 3. Actionable Steps (Cypher Queries for Exploration)

This pass is primarily investigative. We will use Cypher queries to explore the graph.

1.  **List all Node Labels and their Counts**:
    ```cypher
    CALL db.labels() YIELD label
    MATCH (n:`label`) RETURN label, count(n) AS count ORDER BY count DESC
    ```

2.  **List all Relationship Types and their Counts**:
    ```cypher
    CALL db.relationshipTypes() YIELD relationshipType
    MATCH ()-[r:`relationshipType`]->() RETURN relationshipType, count(r) AS count ORDER BY count DESC
    ```

3.  **Inspect Properties of Key Node Types**:
    *   **`:File` nodes**:
        ```cypher
        MATCH (n:File) RETURN DISTINCT keys(n) LIMIT 1
        MATCH (n:File) RETURN n.fileName, n.name, n.id LIMIT 5
        ```
    *   **`:Directory` nodes**:
        ```cypher
        MATCH (n:Directory) RETURN DISTINCT keys(n) LIMIT 1
        MATCH (n:Directory) RETURN n.fileName, n.name, n.id LIMIT 5
        ```
    *   **`:Type:Class` nodes**:
        ```cypher
        MATCH (n:Type:Class) RETURN DISTINCT keys(n) LIMIT 1
        MATCH (n:Type:Class) RETURN n.fqn, n.name, n.sourceFileName LIMIT 5
        ```
    *   **`:Type:Interface`, `:Type:Enum`, `:Type:Annotation`, `:Type:Record`, `:Type:Module`, `:Type:Package` nodes**: (Similar queries for each).
    *   **`:Artifact` nodes**:
        ```cypher
        MATCH (n:Artifact) RETURN DISTINCT keys(n) LIMIT 1
        MATCH (n:Artifact) RETURN n.name, n.version, n.fileName LIMIT 5
        ```

4.  **Inspect Relationships**:
    *   **`[:CONTAINS]` relationships**:
        ```cypher
        MATCH (d:Directory)-[r:CONTAINS]->(n) RETURN d.fileName, type(r), n.fileName, labels(n) LIMIT 10
        // Check for transitivity:
        MATCH (d:Directory)-[:CONTAINS]->(mid:Directory)-[:CONTAINS]->(n) RETURN d.fileName, mid.fileName, n.fileName LIMIT 5
        // Check for Class-Package containment:
        MATCH (p:Package)-[r:CONTAINS]->(t:Type) RETURN p.fqn, type(r), t.fqn, labels(t) LIMIT 5
        ```
    *   **`[:INVOKES]` relationships (method calls)**:
        ```cypher
        MATCH (caller:Method)-[r:INVOKES]->(callee:Method) RETURN caller.fqn, type(r), callee.fqn LIMIT 5
        ```
    *   **`[:DECLARES]` relationships**:
        ```cypher
        MATCH (t:Type)-[r:DECLARES]->(m:Method) RETURN t.fqn, type(r), m.fqn LIMIT 5
        ```
    *   **`[:EXTENDS]` and `[:IMPLEMENTS]` relationships**:
        ```cypher
        MATCH (t:Type)-[r:EXTENDS|IMPLEMENTS]->(base:Type) RETURN t.fqn, type(r), base.fqn LIMIT 5
        ```
    *   **Relationships involving `Artifact` nodes**:
        ```cypher
        MATCH (a:Artifact)-[r]->(n) RETURN a.name, type(r), labels(n), n.fileName, n.fqn LIMIT 5
        ```

## 4. Expected Outcome

A clear understanding of the jQAssistant graph's structure, which will inform the design of subsequent passes, particularly for path normalization, hierarchy reconstruction, and node matching. This pass will confirm the exact property names (e.g., `fileName` vs. `path`) and relationship types used by jQAssistant.
