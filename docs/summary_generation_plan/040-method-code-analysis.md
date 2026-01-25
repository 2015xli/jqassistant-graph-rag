# Plan: 040 - Method Code Analysis and Summary Generation

## 1. Goal

This pass focuses on generating initial summaries for `:Method` nodes. It will extract the source code for each method, generate a detailed `code_analysis` property, and then create a concise `summary` property based on that analysis.

## 2. Rationale

*   **Foundation for Roll-up**: Method summaries are the lowest-level code-centric summaries, forming the foundation for higher-level type and file summaries.
*   **Code-Specific Analysis**: `code_analysis` provides a detailed, LLM-generated understanding of the method's literal function.
*   **Contextual Summary**: The initial `summary` provides a concise overview of the method's purpose.
*   **Direct Source Access**: Leverages the `(Member)-[:WITH_SOURCE]->(SourceFile)` relationship created in Pass 035 for efficient source code retrieval.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve method source code details.
*   Reading source files from the file system.
*   LLM calls (simulated for now) to generate `code_analysis` and `summary` properties.

### Step 3.1: Retrieve Method Source Code and Context

*   **Logic**: Find `:Method` nodes that have `firstLineNumber`, `lastLineNumber`, and are linked to a `:SourceFile` via `[:WITH_SOURCE]`.
*   **Cypher (to get method details and source file path)**:
    ```cypher
    MATCH (m:Method)-[:WITH_SOURCE]->(sf:SourceFile)
    WHERE m.firstLineNumber IS NOT NULL AND m.lastLineNumber IS NOT NULL
    AND sf.absolute_path IS NOT NULL
    RETURN id(m) AS methodId, m.name AS methodName, m.signature AS methodSignature,
           sf.absolute_path AS sourceFilePath, m.firstLineNumber AS firstLine, m.lastLineNumber AS lastLine
    ```
    *   **Note**: `id(m)` is used to uniquely identify the method node for later updates.

### Step 3.2: Extract Code Snippet

*   **Logic**: For each method record retrieved in Step 3.1, read the `sourceFilePath` from the file system and extract the lines between `firstLine` and `lastLine`.
*   **Implementation**: This will be handled by the `_extract_method_code_snippet` method in `CodeAnalyzer`.

### Step 3.3: Generate `code_analysis` for Methods

*   **Logic**: Send the extracted code snippet to an LLM (simulated) with a prompt asking for a detailed code analysis. Store the result in `m.code_analysis`.
*   **LLM Prompt Example (simulated)**: "Analyze the following Java/Kotlin method code and describe its literal function, inputs, and outputs. Focus purely on what the code does, not its purpose in the larger system."
*   **Implementation**: Handled by `_generate_code_analysis` in `CodeAnalyzer`.

### Step 3.4: Generate `summary` for Methods

*   **Logic**: Use the generated `code_analysis` and the method's name/signature to generate a concise `summary` property.
*   **LLM Prompt Example (simulated)**: "Based on the following code analysis, provide a concise summary of this method's purpose."
*   **Implementation**: Handled by `_generate_summary` in `CodeAnalyzer`.

### Step 3.5: Update Neo4j Graph

*   **Logic**: Batch update the `:Method` nodes with the newly generated `code_analysis` and `summary` properties.
*   **Cypher (to update `code_analysis` and `summary`)**:
    ```cypher
    UNWIND $updates AS item
    MATCH (m:Method)
    WHERE id(m) = item.methodId
    SET m.code_analysis = item.code_analysis,
        m.summary = item.summary
    ```

## 4. Expected Outcome

*   `:Method` nodes will have a `code_analysis` property containing a detailed LLM-generated description of their function.
*   `:Method` nodes will have a `summary` property containing a concise LLM-generated description of their purpose.
*   These properties will be used in subsequent passes for rolling up summaries to higher-level nodes.