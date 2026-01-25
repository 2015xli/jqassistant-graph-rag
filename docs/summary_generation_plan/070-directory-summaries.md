# Plan: 070 - Directory Summaries

## 1. Goal

This pass focuses on generating summaries for `:Directory` nodes. It leverages the `[:CONTAINS_SOURCE]` relationships created in Pass 030 to ensure accurate roll-up from immediate children. This pass will:

1.  Generate `summary` properties for `:Directory` nodes.
2.  Incorporate summaries from their direct child `:SourceFile` nodes (from Pass 060) and direct child `:Directory` nodes (from this pass, processed in a bottom-up manner).

## 2. Rationale

*   **Hierarchical Context**: Directory summaries provide a high-level overview of the purpose and contents of code directories, reflecting the project's physical structure.
*   **Accurate Roll-up**: Using `[:CONTAINS_SOURCE]` prevents redundant summarization and ensures summaries are built from the correct immediate children.
*   **Foundation for Project/Package Summaries**: These summaries are crucial for rolling up to the project root or for understanding package structures.
*   **Rolling-Up Logic**: A Directory node will only receive a summary if it has summarized children.
*   **Neo4j `id()` Deprecation**: All queries use `elementId()` for node identification, ensuring compatibility with Neo4j 5.x.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve summaries of direct children.
*   LLM calls to generate `summary` properties.

### Step 3.1: Determine Summarization Order (Bottom-Up by Depth)

*   **Logic**: Summarize directories from the deepest levels first, moving upwards towards the root. This ensures that when a parent directory is summarized, its child directories have already had their summaries generated.
*   **Cypher (to get directories by depth)**:
    ```cypher
    MATCH (d:Directory)
    WHERE d.absolute_path IS NOT NULL AND NOT d:Package
    WITH d, size(split(d.absolute_path, '/')) AS depth
    ORDER BY depth DESC
    RETURN elementId(d) AS id, d.absolute_path AS directoryAbsolutePath, depth
    ```

### Step 3.2: Generate `summary` for Directories

*   **Logic**: For each `:Directory` node in the determined order:
    1.  Gather summaries (`summary` property) of its direct child `:SourceFile` nodes (via `[:CONTAINS_SOURCE]`).
    2.  Gather summaries (`summary` property) of its direct child `:Directory` nodes (via `[:CONTAINS_SOURCE]`).
    3.  If the combined child summaries are empty, skip summary generation.
    4.  Otherwise, combine these child summaries and send this combined context to an LLM with a prompt asking for a concise summary of the directory's purpose and contents. Store the result in `d.summary`.
*   **LLM Prompt Example**: "Based on the following summaries of files and subdirectories contained within this directory, provide a concise summary of its overall purpose and contents."
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $directories AS directoryData
    MATCH (d:Directory)
    WHERE elementId(d) = directoryData.id
    SET d.summary = directoryData.summary
    ```
    *   **Note**: The `elementId(d)` is used for matching as it is guaranteed to be unique for directories.

## 4. Expected Outcome

*   `:Directory` nodes will have a `summary` property, provided they have summarized children.
*   These summaries will accurately reflect the contents of their immediate children, providing a contextual understanding of each directory.
*   These summaries will be used in subsequent passes for rolling up to the project node.
