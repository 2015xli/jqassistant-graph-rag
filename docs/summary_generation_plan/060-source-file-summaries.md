# Plan: 060 - Source File Summaries

## 1. Goal

This pass focuses on generating `summary` properties for `:SourceFile` nodes. These nodes represent the actual `.java` or `.kt` source files in the project. The summary will incorporate information from the top-level `:Type` nodes that are declared within that source file (from Pass 050).

## 2. Rationale

*   **File-Level Context**: Source file summaries provide a high-level overview of the purpose and contents of individual source files.
*   **Foundation for Directory Summaries**: These summaries are crucial for rolling up to higher-level entities like directories.
*   **Agent Navigation**: Allows an AI agent to quickly understand a file's purpose without reading its entire content.
*   **Rolling-Up Logic**: A SourceFile node will only receive a summary if it contains summarized Type nodes.
*   **Neo4j `id()` Deprecation**: All queries use `elementId()` for node identification, ensuring compatibility with Neo4j 5.x.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve summaries of contained types.
*   LLM calls (simulated for now) to generate `summary` properties.

### Step 3.1: Retrieve Source File Context (Summaries of Contained Types)

*   **Logic**: Find `:SourceFile` nodes. For each `:SourceFile` node, find all `:Type` nodes that it contains (via `[:WITH_SOURCE]` in reverse) and retrieve their `summary` properties (generated in Pass 050).
*   **Cypher (to get source file and its contained type summaries)**:
    ```cypher
    MATCH (sf:SourceFile)<-[:WITH_SOURCE]-(t:Type)
    WHERE t.summary IS NOT NULL
    RETURN elementId(sf) AS sourceFileId, sf.absolute_path AS sourceFilePath,
           COLLECT(DISTINCT {typeFqn: t.fqn, typeSummary: t.summary}) AS containedTypeSummaries
    ```

### Step 3.2: Generate `summary` for Source Files

*   **Logic**: For each `:SourceFile` node:
    1.  Combine the `containedTypeSummaries` (from Step 3.1).
    2.  If the combined context is empty (meaning no summarized Type nodes), skip summary generation.
    3.  Otherwise, send this combined context to an LLM (simulated) with a prompt asking for a concise summary of the source file's overall purpose and contents. Store the result in `sf.summary`.
*   **LLM Prompt Example (simulated)**: "Based on the following summaries of types defined within this source file, provide a concise summary of the source file's overall purpose and contents."
*   **Implementation**: Handled by `_generate_source_file_summary` in `CodeAnalyzer`.

### Step 3.3: Update Neo4j Graph

*   **Logic**: Batch update the `:SourceFile` nodes with the newly generated `summary` properties.
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $updates AS item
    MATCH (sf:SourceFile)
    WHERE elementId(sf) = item.sourceFileId
    SET sf.summary = item.summary
    ```

## 4. Expected Outcome

*   `:SourceFile` nodes will have a `summary` property, provided they contain summarized Type nodes.
*   These summaries will incorporate information from the top-level types defined within them, providing a contextual understanding of each source file.
*   These summaries will be used in subsequent passes for rolling up to directories.