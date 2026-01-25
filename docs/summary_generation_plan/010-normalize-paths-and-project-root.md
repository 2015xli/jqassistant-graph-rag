# Plan: 010 - Normalize Paths and Establish Project Root

## 1. Goal

This pass aims to establish a consistent and unambiguous project root within the jQAssistant graph, and to normalize paths for source-code-containing entities. jQAssistant's default graph may lack a single `:Project` node. This pass will:

1.  Identify `:Artifact:Directory` nodes as the true top-level entry points of file system hierarchies.
2.  Create a single `:Project` node to serve as the logical root of our RAG graph.
3.  Label the identified `:Artifact:Directory` nodes as `:Entry` nodes, linking them to the `:Project` node.
4.  For `:Directory` and `:File` nodes (including `:Jar:Artifact` nodes) contained within an `:Entry:Directory` (non-JAR project root), calculate and set an `absolute_path` property that represents their full path on the file system.
5.  Nodes contained within an `:Entry:Jar` (JAR artifact) will retain their `fileName` property as their FQN-like identifier, and no `absolute_path` will be created for them.

## 2. Rationale

*   **Consistent Root**: A single `:Project` node provides a clear starting point for graph traversals and summarization roll-ups.
*   **Consistent Absolute Paths**: Using `absolute_path` everywhere (where applicable) removes the ambiguity of `fileName` and the need to constantly switch between relative and absolute contexts. This simplifies graph traversal and query formulation for the AI agent, especially with multiple entry points.
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

### Step 3.3: Add `absolute_path` Property for `Directory` and `File` Nodes under `:Entry:Directory` (including `:Jar:Artifact` nodes)

*   **Logic**: For `:Directory` and `:File` nodes (including `:Jar:Artifact` nodes) that are contained within an `:Entry:Directory` (i.e., a non-JAR project root), calculate an `absolute_path` property. This `absolute_path` will be the full path on the file system.
    *   For the `Entry:Directory` node itself, `absolute_path` is its `fileName`.
    *   For its descendants, `absolute_path` is constructed by concatenating the `Entry:Directory`'s `fileName` with the descendant's `fileName` (after stripping the descendant's leading `/`).
*   **Cypher**:
    ```cypher
    // First, set absolute_path for the Entry:Directory nodes themselves
    MATCH (entry:Entry:Directory)
    SET entry.absolute_path = entry.fileName
    WITH entry

    // Then, set absolute_path for their descendants
    MATCH (entry)-[:CONTAINS*]->(n) // Find all descendants of an Entry Directory
    WHERE (n:File OR n:Directory OR n:Jar) AND n.fileName IS NOT NULL
    AND NOT (n)<-[:CONTAINS*]-(:Jar) // Exclude nodes that are contained by any Jar node
    WITH n, entry
    // Construct absolute path: entry.fileName + n.fileName (without its leading '/')
    SET n.absolute_path = entry.fileName + '/' + substring(n.fileName, 1)
    RETURN count(n) AS pathsNormalized
    ```
    *   **Note**: The `substring(n.fileName, 1)` correctly removes the leading `/` from the descendant's `fileName`.
    *   **Important**: Nodes contained within an `:Entry:Jar` will *not* receive an `absolute_path` property in this step, as their `fileName` already serves as their FQN-like identifier.

## 4. Expected Outcome

*   A single `:Project` node exists.
*   All `:Artifact:Directory` nodes are labeled `:Entry` and linked to `:Project`.
*   `:Directory` and `:File` nodes (including `:Jar:Artifact` nodes) contained within an `:Entry:Directory` will have a new `absolute_path` property that is consistent and represents their full file system path.
*   Nodes contained within an `:Entry:Jar` will retain their `fileName` as their primary identifier.