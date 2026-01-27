# Design: SourceFileLinker

## 1. Purpose and Role

The `SourceFileLinker` is a crucial enrichment component that bridges the gap between the two worlds of the project: the world of compiled bytecode (represented by jQAssistant's graph) and the world of source code (the `.java` and `.kt` files on disk).

jQAssistant primarily creates `:Type` nodes (like `:Class`, `:Interface`) based on its analysis of `.class` files, and it populates them with a `fqn` (Fully Qualified Name). However, it does not create a reliable, direct link to the source file that defines that type. The `SourceFileLinker`'s job is to create this missing link. It does this by parsing the entire source tree, identifying the FQNs of the types defined in each file, and then creating `[:WITH_SOURCE]` relationships in the graph between the existing `:Type` nodes and the `:File` nodes that represent their source.

## 2. Workflow

1.  **Initialization**: The linker is initialized with a `Neo4jManager` and the project's root `Path`.
2.  **Source Parsing (`_parse_source_files`)**: The main `run()` method first calls a private method to parse all source files.
    *   It instantiates `JavaSourceParser` and `KotlinSourceParser`.
    *   Each parser walks the file system from the project root, finding all files with the relevant extension (`.java` or `.kt`).
    *   For each source file, it uses the `tree-sitter` library to parse the code into an Abstract Syntax Tree (AST).
    *   It traverses the AST to find the package declaration and the names of all top-level type declarations (classes, interfaces, enums, etc.).
    *   It constructs the FQN for each type found.
    *   The result is a list of metadata dictionaries, where each dictionary contains the file's path and a list of the FQNs it defines.
3.  **Graph Enrichment (`_enrich_graph`)**:
    *   The list of source file metadata is passed to this method.
    *   The method processes the metadata in batches to avoid overwhelming the database with a single massive transaction.
    *   For each batch, it executes a Cypher query. This query unwinds the metadata, finds the `:File` node matching the source file path, finds the `:Type` nodes matching the FQNs, and then `MERGE`s a `[:WITH_SOURCE]` relationship between them.

## 3. Key Methods

-   `run()`: The main public method that orchestrates the entire linking process.
-   `_parse_source_files()`: Manages the instantiation of the language-specific parsers and aggregates their results.
-   `_enrich_graph(source_metadata)`: Takes the parsed metadata and executes the batched Cypher queries to update the Neo4j graph.
-   **Language Parsers (`JavaSourceParser`, `KotlinSourceParser`)**: These are helper classes that contain the specific `tree-sitter` logic for parsing a single language. They are responsible for the details of AST traversal and FQN construction.

## 4. Dependencies

-   `neo4j_manager.Neo4jManager`: To write the new `[:WITH_SOURCE]` relationships to the graph.
-   `java_source_parser.JavaSourceParser` & `kotlin_source_parser.KotlinSourceParser`: To perform the actual source code parsing.
-   External `tree-sitter` libraries (`tree-sitter-java`, `tree-sitter-kotlin`): These are the underlying parsing engines.

## 5. Design Rationale

-   **Bridging Two Worlds**: This component is the essential link that makes a source-code-aware analysis possible. Without it, the graph would only represent the compiled structure, and it would be impossible to find the source code for a given method or to generate summaries based on the actual implementation.
-   **Static Analysis with `tree-sitter`**: The use of `tree-sitter` provides a fast, robust, and language-aware way to parse source code. It is much more reliable than using regular expressions and avoids the complexity of a full compilation.
-   **Decoupling Parsing Logic**: The parsing logic is separated into language-specific classes (`JavaSourceParser`, `KotlinSourceParser`). This is a clean design that makes it easy to add support for new languages in the future (e.g., by adding a `PythonSourceParser`) without changing the core `SourceFileLinker` logic.
-   **Batch Processing**: The `_enrich_graph` method processes the updates in batches. This is a crucial performance consideration for large projects with thousands of source files, as it prevents memory issues and transaction timeouts in the database.
