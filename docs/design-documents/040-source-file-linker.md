# Design: SourceFileLinker

## 1. Purpose and Role

The `SourceFileLinker` is a crucial enrichment component that bridges the gap between the logical graph (e.g., `:Type` nodes) and the physical source code files on disk.

Its primary responsibility is to establish the vital `[:WITH_SOURCE]` relationship. It does this by first using language-specific parsers to analyze the content of source files, extracting the Fully Qualified Names (FQNs) of the types they contain. It then uses this information to create links in the graph from the existing `:Type` and `:Member` nodes to the `:SourceFile` node that defines them.

## 2. Workflow

1.  **Initialization**: The linker is initialized with a `Neo4jManager` instance.
2.  **Source Parsing (`_parse_source_files`)**: The `link_types_to_source_files` pass first calls a private method to parse all source files.
    *   It instantiates `JavaSourceParser` and `KotlinSourceParser`.
    *   Crucially, each parser **queries the Neo4j graph** for nodes already labeled as `:SourceFile` and retrieves their `absolute_path`. This is a change from the previous design and leverages the pre-processing work done by the `GraphBasicNormalizer`.
    *   For each source file found, it uses the `tree-sitter` library to parse the code and extract the FQNs of all top-level types.
    *   The result is a list of metadata dictionaries, where each dictionary contains the file's `absolute_path` and a list of the FQNs it defines.
3.  **Type Linking (`link_types_to_source_files`)**:
    *   The list of source file metadata is processed in batches.
    *   For each batch, it executes a Cypher query that finds the `:SourceFile` node by its `absolute_path`, finds the `:Type` nodes by their FQNs, and then `MERGE`s a `[:WITH_SOURCE]` relationship between them.
4.  **Member Linking (`link_members_to_source_files`)**:
    *   This pass executes a separate Cypher query that leverages the newly created relationships. It finds `:Member` nodes, traverses to their declaring `:Type`, follows the `[:WITH_SOURCE]` link to the `:SourceFile`, and creates a direct `[:WITH_SOURCE]` link from the member to the file for convenient access.

## 3. Key Methods

-   `link_types_to_source_files()`: The public method that orchestrates the parsing and type-linking process.
-   `link_members_to_source_files()`: The public method that links members to their source files.
-   `_parse_source_files()`: A private helper that manages the language-specific parsers.
-   `_enrich_graph_with_types()`: A private helper that executes the batched Cypher queries for type linking.

## 4. Dependencies

-   `neo4j_manager.Neo4jManager`: To read `:SourceFile` nodes and write the new `[:WITH_SOURCE]` relationships.
-   `java_source_parser.JavaSourceParser` & `kotlin_source_parser.KotlinSourceParser`: To perform the source code parsing.

## 5. Design Rationale

-   **Graph-Driven Parsing**: By querying the graph for `:SourceFile` nodes, the linker is tightly integrated into the overall workflow. It operates on a known set of files that have been explicitly identified as source code, which is more robust and efficient than scanning the entire filesystem.
-   **Decoupling**: The parsing logic remains cleanly separated into language-specific classes, making the system extensible.
-   **Batch Processing**: Updates are processed in batches to ensure performance and stability on large projects.