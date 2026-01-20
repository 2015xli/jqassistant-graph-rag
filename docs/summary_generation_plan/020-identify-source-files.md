# Plan: 020 - Identify and Label Source Files

## 1. Goal

jQAssistant's graph can be confusing as it labels many different kinds of nodes as `:File` (e.g., `.java` files, `.kt` files, `.class` files, `.jar` files). For our RAG purposes, we need to clearly distinguish between source code files (Java/Kotlin) and other types of files. This pass will:

1.  Identify all `:File` nodes that represent actual Java (`.java`) or Kotlin (`.kt`) source code files.
2.  Label these identified nodes with a new, more specific label: `:SourceFile`.
3.  Ensure these `:SourceFile` nodes are correctly identified using their `fileName` or `relative_path` property (if `relative_path` exists).

## 2. Rationale

*   **Clarity**: The `:SourceFile` label provides unambiguous identification of nodes containing human-readable source code, which is essential for AI agent interaction.
*   **Targeted Summarization**: It allows subsequent summarization passes to specifically target and process only source code files.
*   **Consistency**: Aligns the graph with the output of our `java_source_parser.py` and `kotlin_source_parser.py`.

## 3. Actionable Steps (Cypher Queries)

This pass will involve a single Cypher query.

### Step 3.1: Label `:File` Nodes as `:SourceFile`

*   **Logic**: Find `:File` nodes whose `fileName` (for nodes without `relative_path`, e.g., within JARs) or `relative_path` (for nodes under `:Entry:Directory`) ends with `.java` or `.kt`. Add the `:SourceFile` label to them.
*   **Cypher**:
    ```cypher
    MATCH (f:File)
    WHERE (f.relative_path IS NOT NULL AND (f.relative_path ENDS WITH '.java' OR f.relative_path ENDS WITH '.kt'))
       OR (f.relative_path IS NULL AND (f.fileName ENDS WITH '.java' OR f.fileName ENDS WITH '.kt'))
    SET f:SourceFile
    RETURN count(f) AS sourceFilesLabeled
    ```
    *   **Note**: This query prioritizes `relative_path` if it exists (for files under `Entry:Directory`) and falls back to `fileName` otherwise (for files within JARs, whose `fileName` might still end with `.java` or `.kt` if they are source files directly embedded in the JAR, though this is less common for compiled JARs).

## 4. Expected Outcome

*   All `:File` nodes representing Java or Kotlin source code files will have the additional label `:SourceFile`.
*   This new label will be used in subsequent passes to filter for actual source code files.
