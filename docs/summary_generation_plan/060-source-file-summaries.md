# Plan: 060 - Source File Summaries

## 1. Goal

This pass focuses on generating summaries for `:SourceFile` nodes. These nodes represent the actual `.java` or `.kt` source files in the project. This pass will:

1.  Generate `summary` properties for `:SourceFile` nodes.
2.  Incorporate summaries from the top-level `:Type` nodes (Class, Interface, Enum, Annotation, Record) that are declared within that source file (from Pass 050).

## 2. Rationale

*   **File-Level Context**: Source file summaries provide a high-level overview of the purpose and contents of individual source files.
*   **Foundation for Directory Summaries**: These summaries are crucial for rolling up to higher-level entities like directories.
*   **Agent Navigation**: Allows an AI agent to quickly understand a file's purpose without reading its entire content.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve summaries of contained types.
*   LLM calls to generate `summary` properties.

### Step 3.1: Retrieve Source File Context (Summaries of Contained Types)

*   **Logic**: Find `:SourceFile` nodes. For each `:SourceFile` node, find all `:Type` nodes that it contains (via `[:WITH_SOURCE]` in reverse) and retrieve their `summary` properties (generated in Pass 050).
*   **Cypher (to get source file and its contained type summaries)**:
    ```cypher
    MATCH (sf:SourceFile)<-[:WITH_SOURCE]-(type:Type)
    WHERE type.summary IS NOT NULL
    RETURN sf.fileName AS sourceFilePath, COLLECT(type.summary) AS containedTypeSummaries
    LIMIT 1000 // Process in batches
    ```

### Step 3.2: Generate `summary` for Source Files

*   **Logic**: For each `:SourceFile` node:
    1.  Combine the `containedTypeSummaries` (from Step 3.1).
    2.  Send this combined context to an LLM with a prompt asking for a concise summary of the source file's purpose and contents. Store the result in `sf.summary`.
*   **LLM Prompt Example**: "Based on the following summaries of types defined within this source file, provide a concise summary of the source file's overall purpose and contents."
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $sourceFiles AS fileData
    MATCH (sf:SourceFile {fileName: fileData.sourceFilePath})
    SET sf.summary = fileData.summary
    ```

## 4. Expected Outcome

*   `:SourceFile` nodes will have a `summary` property.
*   These summaries will incorporate information from the top-level types defined within them, providing a contextual understanding of each source file.
*   These summaries will be used in subsequent passes for rolling up to directories.
