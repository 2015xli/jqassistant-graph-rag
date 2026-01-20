# Plan: 040 - Method Code Analysis and Summary Generation

## 1. Goal

This pass focuses on generating initial summaries for `:Method` nodes. As per user feedback, jQAssistant's `:Method` nodes do not directly have a `fileName` property, and we need to generate `code_analysis` (not `codeSummary`) for them. This pass will:

1.  For each `:Method` node, identify its declaring `:Type` node.
2.  From the declaring `:Type` node, find its associated `:SourceFile` node (via `[:WITH_SOURCE]`).
3.  Read the source code of the `:SourceFile` and extract the specific code snippet corresponding to the method's body.
4.  Generate a `code_analysis` property for the `:Method` node based on this extracted code snippet.
5.  Generate an initial `summary` for the `:Method` node based on its `code_analysis` and its name/signature, without yet incorporating context from its parent type.

## 2. Rationale

*   **Foundation for Roll-up**: Method summaries are the lowest-level code-centric summaries, forming the foundation for higher-level type and file summaries.
*   **Code-Specific Analysis**: `code_analysis` provides a detailed, LLM-generated understanding of the method's literal function.
*   **Contextual Summary**: The initial `summary` provides a concise overview of the method's purpose.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve method source code.
*   LLM calls to generate `code_analysis` and `summary` properties.

### Step 3.1: Retrieve Method Source Code and Context

*   **Logic**: Find `:Method` nodes, traverse to their declaring `:Type` and then to the `:SourceFile`. Use the `fileName` of the `:SourceFile` and the method's `signature` (or other properties) to locate the method's body within the file.
*   **Cypher (to get method details and source file path)**:
    *   **Cypher (to get method details and source file path)**:
    ```cypher
    MATCH (type:Type)-[:DECLARES]->(method:Method)-[:WITH_SOURCE]->(sourceFile:SourceFile)
    WHERE method.signature IS NOT NULL AND sourceFile.fileName IS NOT NULL
    RETURN method.fqn AS methodFqn, method.signature AS methodSignature, sourceFile.fileName AS sourceFilePath
    LIMIT 1000 // Process in batches
    ```
    *   **Note**: jQAssistant's schema for methods might be complex. We need to verify the exact relationship between `:Method` and `:Type` (e.g., `[:DECLARES]`, `[:CONTAINS]`, `[:HAS_METHOD]`). The `fqn` of the method might also be useful.
    *   **Challenge**: jQAssistant's `:Method` nodes typically have `signature` and `name` but often lack precise `body_location` (start/end lines) in the source file. This means we might need to use heuristics (e.g., regex matching the signature within the file) or a more advanced source code parser (like `tree-sitter`) to extract the exact method body. For this plan, we assume we can extract the method body given its signature and source file.

### Step 3.2: Generate `code_analysis` for Methods

*   **Logic**: For each method, extract its source code snippet. Send this snippet to an LLM with a prompt asking for a detailed code analysis. Store the result in `method.code_analysis`.
*   **LLM Prompt Example**: "Analyze the following Java/Kotlin method code and describe its literal function, inputs, and outputs. Focus purely on what the code does, not its purpose in the larger system."
*   **Cypher (to update `code_analysis`)**:
    ```cypher
    UNWIND $methods AS methodData
    MATCH (m:Method {fqn: methodData.methodFqn})
    SET m.code_analysis = methodData.analysis
    ```

### Step 3.3: Generate `summary` for Methods

*   **Logic**: For each method, use its `code_analysis` (from Step 3.2) and its name/signature to generate a concise `summary` property. This summary should describe the method's purpose.
*   **LLM Prompt Example**: "Based on the following code analysis, provide a concise summary of this method's purpose."
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $methods AS methodData
    MATCH (m:Method {fqn: methodData.methodFqn})
    SET m.summary = methodData.summary
    ```

## 4. Expected Outcome

*   `:Method` nodes will have a `code_analysis` property containing a detailed LLM-generated description of their function.
*   `:Method` nodes will have a `summary` property containing a concise LLM-generated description of their purpose.
*   These properties will be used in subsequent passes for rolling up summaries to higher-level nodes.
