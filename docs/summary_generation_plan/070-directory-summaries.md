# Plan: 070 - Directory Summaries

## 1. Goal

This pass focuses on generating summaries for `:Directory` nodes. It leverages the `[:CONTAINS_DIRECT]` relationships created in Pass 030 to ensure accurate roll-up from immediate children. This pass will:

1.  Generate `summary` properties for `:Directory` nodes.
2.  Incorporate summaries from their direct child `:SourceFile` nodes (from Pass 060) and direct child `:Directory` nodes (from this pass, processed in a bottom-up manner).

## 2. Rationale

*   **Hierarchical Context**: Directory summaries provide a high-level overview of the purpose and contents of code directories, reflecting the project's physical structure.
*   **Accurate Roll-up**: Using `[:CONTAINS_DIRECT]` prevents redundant summarization and ensures summaries are built from the correct immediate children.
*   **Foundation for Project/Package Summaries**: These summaries are crucial for rolling up to the project root or for understanding package structures.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve summaries of direct children.
*   LLM calls to generate `summary` properties.

### Step 3.1: Determine Summarization Order (Bottom-Up by Depth)

*   **Logic**: Summarize directories from the deepest levels first, moving upwards towards the root. This ensures that when a parent directory is summarized, its child directories have already had their summaries generated.
*   **Cypher (to get directories by depth)**:
    ```cypher
    MATCH (d:Directory)
    WHERE d.relative_path IS NOT NULL
    WITH d, size(split(d.relative_path, '/')) AS depth
    ORDER BY depth DESC
    RETURN d.fileName AS directoryFileName, d.relative_path AS directoryRelativePath, depth
    LIMIT 1000 // Process in batches
    ```

### Step 3.2: Generate `summary` for Directories

*   **Logic**: For each `:Directory` node in the determined order:
    1.  Gather summaries (`summary` property) of its direct child `:SourceFile` nodes (via `[:CONTAINS_DIRECT]`).
    2.  Gather summaries (`summary` property) of its direct child `:Directory` nodes (via `[:CONTAINS_DIRECT]`).
    3.  Combine these child summaries.
    4.  Send this combined context to an LLM with a prompt asking for a concise summary of the directory's purpose and contents. Store the result in `d.summary`.
*   **LLM Prompt Example**: "Based on the following summaries of files and subdirectories contained within this directory, provide a concise summary of its overall purpose and contents."
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $directories AS directoryData
    MATCH (d:Directory {fileName: directoryData.directoryFileName})
    SET d.summary = directoryData.summary
    ```
    *   **Note**: The `fileName` or `relative_path` can be used for matching, but `fileName` is more likely to be indexed by jQAssistant.

## 4. Expected Outcome

*   `:Directory` nodes will have a `summary` property.
*   These summaries will accurately reflect the contents of their immediate children, providing a contextual understanding of each directory.
*   These summaries will be used in subsequent passes for rolling up to the project node.
