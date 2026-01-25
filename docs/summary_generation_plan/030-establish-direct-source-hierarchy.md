# Plan: 030 - Establish Direct Source Hierarchy

## 1. Goal

This pass aims to establish a clear, unified, and direct hierarchical structure for all source-related entities (directories and source files) using a single `[:CONTAINS_SOURCE]` relationship type. This hierarchy will be based on the `absolute_path` property established in Pass 010, making traversal and contextual understanding for RAG purposes intuitive and consistent.

## 2. Rationale

*   **Unified Traversal for AI Agents**: A single `[:CONTAINS_SOURCE]` relationship simplifies how AI agents navigate the source code hierarchy, eliminating the need to differentiate between various "contains" relationship types.
*   **Consistent Pathing**: Leveraging the `absolute_path` property ensures that all source-related nodes can be uniquely identified and their hierarchical relationships derived unambiguously, regardless of multiple entry points.
*   **Direct Parent-Child Links**: Explicitly creates direct parent-child relationships for all source directories and files, which is essential for accurate bottom-up summarization roll-ups.
*   **Project-Wide View**: Provides a clear path from the `:Project` node down to every source directory and file.

## 3. Actionable Steps (Cypher Queries)

This pass will involve several Cypher queries executed sequentially.

### Step 3.1: Link `:Directory` nodes to their direct `:SourceFile` children

*   **Logic**: For each `:SourceFile` node that has an `absolute_path`, determine its parent directory's `absolute_path`. Find the corresponding parent `:Directory` node and create a `[:CONTAINS_SOURCE]` relationship.
*   **Cypher**:
    ```cypher
    MATCH (sf:SourceFile)
    WHERE sf.absolute_path IS NOT NULL
    WITH sf, split(sf.absolute_path, '/') AS pathParts
    WHERE size(pathParts) > 1 // Ensure it's not a top-level file (e.g., "file.java" directly under project root)
    WITH sf, apoc.text.join(pathParts[0..size(pathParts)-1], '/') AS parentAbsolutePath
    MATCH (parent:Directory)
    WHERE parent.absolute_path = parentAbsolutePath
    MERGE (parent)-[r:CONTAINS_SOURCE]->(sf)
    RETURN count(r) AS directSourceFileRelationshipsCreated
    ```
    *   **Note**: This query assumes that `parent.absolute_path` will correctly identify the parent directory.

### Step 3.2: Link `:Directory` nodes to their direct child `:Directory` nodes

*   **Logic**: For each `:Directory` node that has an `absolute_path` and is not a top-level directory, determine its parent directory's `absolute_path`. Find the corresponding parent `:Directory` node and create a `[:CONTAINS_SOURCE]` relationship.
*   **Cypher**:
    ```cypher
    MATCH (childDir:Directory)
    WHERE childDir.absolute_path IS NOT NULL
    AND NOT (childDir:Entry) // Exclude Entry directories as they are linked from Project
    WITH childDir, split(childDir.absolute_path, '/') AS pathParts
    WHERE size(pathParts) > 1 // Ensure it's not a top-level directory
    WITH childDir, apoc.text.join(pathParts[0..size(pathParts)-1], '/') AS parentAbsolutePath
    MATCH (parentDir:Directory)
    WHERE parentDir.absolute_path = parentAbsolutePath
    MERGE (parentDir)-[r:CONTAINS_SOURCE]->(childDir)
    RETURN count(r) AS directDirectoryRelationshipsCreated
    ```
    *   **Note**: We exclude `Entry` directories here because they will be linked directly from the `:Project` node in the next step.

### Step 3.3: Link `:Project` node to top-level `:Directory` and `:SourceFile` nodes

*   **Logic**: Identify `:Directory` and `:SourceFile` nodes that are directly under the project root (i.e., their `absolute_path` is the `Entry:Directory`'s `fileName` + `/` + `top_level_name`). Create a `[:CONTAINS_SOURCE]` relationship from the `:Project` node to these top-level entities.
*   **Cypher**:
    ```cypher
    MATCH (p:Project)-[:CONTAINS_ENTRY]->(entry:Entry:Directory) // Get the project and its entry points
    MATCH (child)
    WHERE (child:Directory OR child:SourceFile)
    AND child.absolute_path IS NOT NULL
    AND child.absolute_path STARTS WITH entry.fileName + '/' // Ensure it's a descendant of this entry
    AND size(split(substring(child.absolute_path, size(entry.fileName) + 1), '/')) = 1 // Ensure it's a direct child of the entry
    MERGE (p)-[r:CONTAINS_SOURCE]->(child)
    RETURN count(r) AS topLevelRelationshipsCreated
    ```
    *   **Note**: This query links top-level directories and source files directly to the `:Project` node via the `[:CONTAINS_SOURCE]` relationship. It uses the `entry.fileName` to correctly identify the top-level children.

## 4. Expected Outcome

*   A unified `[:CONTAINS_SOURCE]` relationship will represent the direct parent-child hierarchy for all source directories and source files.
*   The `:Project` node will be directly linked to its top-level source directories and source files via `[:CONTAINS_SOURCE]`.
*   All source-related nodes will have an `absolute_path` property, making their location unambiguous.
