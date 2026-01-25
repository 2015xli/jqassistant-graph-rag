# Plan: 020 - Identify and Label Source Files

## 1. Goal

jQAssistant's graph can be confusing as it labels many different kinds of nodes as `:File` (e.g., `.java` files, `.kt` files, `.class` files, `.jar` files). For our RAG purposes, we need to clearly distinguish between source code files (Java/Kotlin) and other types of files. This pass will:

1.  Identify all `:File` nodes that represent actual Java (`.java`) or Kotlin (`.kt`) source code files using the `absolute_path` property created in Pass 010.
2.  Label these identified nodes with a new, more specific label: `:SourceFile`.

## 2. Rationale

*   **Clarity**: The `:SourceFile` label provides unambiguous identification of nodes containing human-readable source code, which is essential for AI agent interaction.
*   **Targeted Summarization**: It allows subsequent summarization passes to specifically target and process only source code files.
*   **Consistency**: Aligns the graph with the output of our `java_source_parser.py` and `kotlin_source_parser.py`, and leverages the consistent `absolute_path` property.

## 3. Actionable Steps (Cypher Queries)

This pass will involve a single Cypher query.

### Step 3.1: Label `:File` Nodes as `:SourceFile`

*   **Logic**: Find `:File` nodes whose `absolute_path` property ends with `.java` or `.kt`. Add the `:SourceFile` label to them. This primarily targets files within an `:Entry:Directory` structure.
*   **Cypher**:
    ```cypher
    MATCH (f:File)
    WHERE f.absolute_path IS NOT NULL 
      AND (f.absolute_path ENDS WITH '.java' OR f.absolute_path ENDS WITH '.kt')
    SET f:SourceFile
    RETURN count(f) AS sourceFilesLabeled
    ```
    *   **Note**: This query relies on the `absolute_path` property created in Pass 010, ensuring we only label files that are part of the analyzed source tree, not files inside JARs that might coincidentally have source-like names.

## 4. Expected Outcome

*   All `:File` nodes representing Java or Kotlin source code files within the project's source directories will have the additional label `:SourceFile`.
