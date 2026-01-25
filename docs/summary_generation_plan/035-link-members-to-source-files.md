# Plan: 035 - Link Members to Source Files

## 1. Goal

This pass aims to create direct `[:WITH_SOURCE]` relationships from `:Method` and `:Field` nodes to their corresponding `:SourceFile` nodes. This is a crucial intermediate step to simplify subsequent passes (like Pass 040: Method Code Analysis) that need to access the source code of individual members.

## 2. Rationale

*   **Direct Source Code Access**: Currently, to find the source code for a `:Method` or `:Field` node, one must traverse `(Member)<-[:DECLARES]-(Type)-[:WITH_SOURCE]->(SourceFile)`. This multi-hop traversal is inefficient and complex for frequent access.
*   **Simplified Queries**: By creating a direct `(Member)-[:WITH_SOURCE]->(SourceFile)` relationship, subsequent queries can directly access the `SourceFile` node from the `Member` node, streamlining code extraction and analysis.
*   **Consistency**: Aligns the member-to-source linking with the existing `Type`-to-`SourceFile` linking.

## 3. Actionable Steps (Cypher Query)

This pass will involve a single Cypher query.

### Step 3.1: Create `[:WITH_SOURCE]` relationships from `:Member` to `:SourceFile`

*   **Logic**:
    1.  Match all `:Member` nodes (which include `:Method` and `:Field`).
    2.  Find their declaring `:Type` node using the `[:DECLARES]` relationship.
    3.  From that `:Type` node, find the associated `:SourceFile` node using the existing `[:WITH_SOURCE]` relationship (created in Pass 001).
    4.  Create a new `[:WITH_SOURCE]` relationship directly from the `:Member` node to that `:SourceFile` node.
*   **Cypher**:
    ```cypher
    MATCH (type:Type)-[:DECLARES]->(member:Member)
    MATCH (type)-[:WITH_SOURCE]->(sourceFile:SourceFile)
    MERGE (member)-[r:WITH_SOURCE]->(sourceFile)
    RETURN count(r) AS memberSourceFileRelationshipsCreated
    ```

## 4. Expected Outcome

*   All `:Method` and `:Field` nodes that have a declaring `:Type` and whose `:Type` is linked to a `:SourceFile` will have a direct `[:WITH_SOURCE]` relationship to that `:SourceFile`.
*   This new relationship will enable more efficient queries for extracting member-level source code.
