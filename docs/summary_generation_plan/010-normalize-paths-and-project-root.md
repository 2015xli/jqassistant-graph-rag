# Plan: 010 - Normalize Paths and Establish Project Root

## 1. Goal

This pass aims to establish a consistent and unambiguous project root within the jQAssistant graph, and to normalize paths for source-code-containing entities. jQAssistant's default graph may lack a single `:Project` node. This pass will:

1.  Identify `:Artifact:Directory` nodes as the true top-level entry points of file system hierarchies.
2.  Create a single `:Project` node to serve as the logical root of our RAG graph.
3.  Label the identified `:Artifact:Directory` nodes as `:Entry` nodes, linking them to the `:Project` node.
4.  For `:Directory` and `:File` nodes (including `:Jar:Artifact` nodes) contained within an `:Entry:Directory` (non-JAR project root), calculate and set a `relative_path` property that is truly relative to that `:Entry` node.
5.  Nodes contained within an `:Entry:Jar` (JAR artifact) will retain their `fileName` property as their FQN-like identifier, and no `relative_path` will be created for them.

## 2. Rationale

*   **Consistent Root**: A single `:Project` node provides a clear starting point for graph traversals and summarization roll-ups.
*   **Normalized Paths**: A consistent `relative_path` property (where applicable) simplifies matching with parsed source code metadata and enables reliable reconstruction of direct parent-child hierarchies.
*   **Clarity**: The `:Entry` label clearly marks the top-level source/module/artifact roots.
*   **jQAssistant Specifics**: Adapts to jQAssistant's use of `:Artifact` nodes as hierarchy roots and the dual nature of `fileName` (filesystem path vs. FQN-like).

## 3. Actionable Steps (Cypher Queries)

This pass will involve several Cypher queries executed sequentially.

### Step 3.1: Create the `:Project` Node

*   **Logic**: Create a single `:Project` node if it doesn't already exist. We can use a placeholder name or derive it from the project path provided during enrichment.
*   **Cypher**:
    ```cypher
    MERGE (p:Project {name: $projectName})
    ON CREATE SET p.creationTimestamp = datetime()
    RETURN p
    ```
    *   `$projectName`: A parameter representing the name of the project (e.g., derived from the base name of the `project_path` argument).

### Step 3.2: Identify and Label `:Entry` Nodes (from `:Artifact:Directory` nodes)

*   **Logic**: Find `:Artifact` nodes that are also `:Directory` nodes. Label them as `:Entry`. Link them to the `:Project` node.
*   **Cypher**:
    ```cypher
    MATCH (a:Artifact:Directory) // Only Artifacts that are also Directories
    SET a:Entry // Label them as Entry points
    WITH a
    MATCH (p:Project {name: $projectName})
    MERGE (p)-[:CONTAINS_ENTRY]->(a) // Link to the Project node
    RETURN count(a) AS entryNodesCreated
    ```

### Step 3.3: Add `relative_path` Property for `Directory` and `File` Nodes under `:Entry:Directory` (including `:Jar:Artifact` nodes)

*   **Logic**: For `:Directory` and `:File` nodes (including `:Jar:Artifact` nodes) that are contained within an `:Entry:Directory` (i.e., a non-JAR project root), calculate a `relative_path` property. This `relative_path` will be truly relative to the `Entry:Directory`'s `fileName`, with any leading `/` stripped.
*   **Cypher**:
    ```cypher
    MATCH (entry:Entry:Directory)-[:CONTAINS*]->(n) // Find all descendants of an Entry Directory
    WHERE (n:File OR n:Directory OR n:Jar) AND n.fileName IS NOT NULL
    AND NOT n:Artifact // Exclude Artifacts themselves from getting relative_path if they are also File/Directory
    WITH n, entry
    // Calculate relative path: strip entry's absolute path from node's absolute path
    // Ensure leading '/' is removed if present in the result
    SET n.relative_path = CASE
                            WHEN n.fileName STARTS WITH entry.fileName THEN
                                // Strip entry.fileName and then strip leading '/' if present
                                substring(n.fileName, size(entry.fileName))
                            ELSE n.fileName // Fallback, though should not happen for descendants
                          END
    SET n.relative_path = CASE
                            WHEN n.relative_path STARTS WITH '/' THEN substring(n.relative_path, 1)
                            ELSE n.relative_path
                          END
    RETURN count(n) AS pathsNormalized
    ```
    *   **Note**: The `substring(n.fileName, size(entry.fileName))` correctly handles stripping the prefix. If `entry.fileName` is `/foo` and `n.fileName` is `/foo/bar`, this results in `/bar`. The subsequent `substring(n.relative_path, 1)` then removes the leading `/`.
    *   **Important**: Nodes contained within an `:Entry:Jar` will *not* receive a `relative_path` property in this step, as their `fileName` already serves as their FQN-like identifier. The `relative_path` is for the `Jar` node itself, not its contents.

## 4. Expected Outcome

*   A single `:Project` node exists.
*   All `:Artifact:Directory` nodes are labeled `:Entry` and linked to `:Project`.
*   `:Directory` and `:File` nodes (including `:Jar:Artifact` nodes) contained within an `:Entry:Directory` will have a new `relative_path` property that is consistent and truly relative to their respective `:Entry` node.
*   Nodes contained within an `:Entry:Jar` will retain their `fileName` as their primary identifier.
