# jQAssistant Graph RAG: Summary Generation Plan

This document outlines the high-level plan for generating AI-enriched summaries and embeddings for a Neo4j graph produced by jQAssistant. The plan addresses the unique characteristics of jQAssistant's graph model, particularly its representation of file systems and Java/Kotlin types, to create a robust and semantically rich RAG (Retrieval-Augmented Generation) graph.

## Core Principles

The summarization process adheres to the following principles:

*   **Bottom-Up, Pass-Based**: Summaries are generated iteratively, starting from the lowest-level code constructs (methods) and rolling up to higher-level entities (types, files, directories, packages, project).
*   **Contextual Summaries**: Each summary incorporates information from its children and its immediate graph context, providing a holistic understanding.
*   **Dynamic Roll-up Logic**: The process is designed to adapt to jQAssistant's graph structure, including reconstructing direct hierarchies where necessary.
*   **Dual-Track Summarization**: The strategy supports both source-code-centric and package-centric analysis paths.

## Addressing jQAssistant Specifics

jQAssistant's graph model presents several challenges that require specific handling:

1.  **`fileName` Property**: jQAssistant uses `fileName` (relative path with leading `/`) for files and directories, not a generic `path` property.
2.  **Transitive `CONTAINS`**: The `[:CONTAINS]` relationship from a `:Directory` node is transitive, linking to all descendants, not just direct children. This necessitates reconstructing direct parent-child links.
3.  **Confusing `File` and `Directory` Labels**: jQAssistant can label classes and directories as `:File`, leading to ambiguity. We will introduce a `:SourceFile` label for clarity.
4.  **No Explicit `:Project` Node**: jQAssistant doesn't create a single `:Project` node by default. We will create one and link it to top-level directories.
5.  **Jar File Representation**: `:Jar` nodes act as containers for packages and types. Summaries for these will be handled carefully, potentially skipped or made metadata-only.
6.  **Neo4j `id()` Deprecation**: Neo4j 5.x deprecates the `id()` function. All queries have been updated to use `elementId()` for node identification.

## Multi-Pass Summarization Workflow

The summarization will proceed through a series of distinct passes, each building upon the results of the previous ones.

### Preparatory Passes: Graph Normalization and Clarification

*   **005-initial-schema-analysis.md**: Initial analysis of the jQAssistant schema to understand node labels, properties, and relationships.
*   **010-normalize-paths-and-project-root.md**:
    *   Identify top-level `:Directory` nodes (potential project roots).
    *   Label them as `:Entry`.
    *   Create a single `:Project` node and link it to these `:Entry` nodes.
    *   Ensure all `:File` and `:Directory` nodes under an `:Entry:Directory` have a consistent `absolute_path` property.
*   **020-identify-source-files.md**:
    *   Identify `:File` nodes that correspond to `.java` or `.kt` source files using their `absolute_path`.
    *   Label them as `:SourceFile` to distinguish them from other `:File` nodes (e.g., `.class` files, `.jar` files).
*   **030-establish-direct-source-hierarchy.md**:
    *   Reconstruct the *direct* parent-child relationships for directories and source files using `absolute_path` properties.
    *   Create new `[:CONTAINS_SOURCE]` relationships between a `:Directory` and its immediate child `:SourceFile` or `:Directory` nodes, and from the `:Project` to top-level items. This is crucial for accurate roll-up.

### Core Summarization Passes: Bottom-Up Roll-up

*   **040-method-code-analysis.md**:
    *   Generate `code_analysis` for `:Method` nodes.
    *   Generate `summary` for `:Method` nodes based on their `code_analysis` and context from caller/callee methods.
*   **050-type-summaries.md**:
    *   Generate `summary` for `:Type` nodes (Class, Interface, Enum, Record).
    *   Summarization order will respect inheritance/implementation hierarchies, ensuring parent summaries are generated before children.
    *   Summaries will incorporate method summaries (from Pass 040) and parent type summaries.
    *   **Crucially, a Type node will only receive a summary if it has summarized methods or parent types (rolling-up logic).** This also correctly handles external types (e.g., `java.lang.Object`) that might not have specific labels like `:Class`, `:Interface`, etc., by matching on the generic `:Type` label.
*   **060-source-file-summaries.md**:
    *   Generate `summary` for `:SourceFile` nodes by rolling up summaries from the `:Type` nodes they contain (via `[:WITH_SOURCE]` in reverse).
    *   **A SourceFile node will only receive a summary if it contains summarized Type nodes (rolling-up logic).**
*   **070-directory-summaries.md**:
    *   Generate `summary` for `:Directory` nodes by rolling up summaries from their *direct* children (`:SourceFile` and `:Directory`) using the newly created `[:CONTAINS_SOURCE]` relationships.
    *   **A Directory node will only receive a summary if it has summarized children (rolling-up logic).**
*   **080-package-summaries.md**:
    *   Generate `summary` for `:Package` nodes.
    *   Summaries will roll up from the `:Type` nodes that belong to them.
    *   Clarify the distinction between `:Package` and `:Directory` nodes in jQAssistant.
*   **090-jar-summaries.md**:
    *   This pass will be skipped for now, as per user's request, or generate a very high-level metadata-only summary if deemed necessary later.

### Finalization Passes

*   **100-project-summary.md**:
    *   Generate `summary` for the single `:Project` node by rolling up from top-level `:Entry` directories.
*   **110-add-entity-label-and-embeddings.md**:
    *   Add the generic `:Entity` label to all nodes that have a `summary` property.
    *   Create a unified vector index on `summaryEmbedding` for `:Entity` nodes.
*   **120-final-cleanup.md**:
    *   Any final graph cleanup or property adjustments.
