# Design: PackageSummarizer

## 1. Purpose and Role

The `PackageSummarizer` is a hierarchical summarizer responsible for generating summaries for the logical package structure of the project. It operates on the clean, validated `[:CONTAINS_CLASS]` hierarchy created by the `PackageDataNormalizer`.

Its goal is to "roll up" information from individual types to provide a high-level overview of what each package and dependency (e.g., JAR file) contributes to the project. This component works in tandem with the `DirectorySummarizer`, which handles the source code hierarchy.

## 2. Workflow

The `PackageSummarizer` uses a robust, two-phase, bottom-up approach to ensure that child summaries are always generated before their parents.

### Phase 1: Summarize Internal Packages

-   **What**: Generates summaries for all the individual `:Package` nodes that are nested inside a `:ClassTree` container.
-   **How**:
    1.  It executes a Cypher query to find all `:Package` nodes that are descendants of a `:ClassTree` via the `[:CONTAINS_CLASS*]` relationship.
    2.  Crucially, it orders these packages by the depth of their `fqn` (e.g., `com.myproject.utils` is deeper than `com.myproject`), from deepest to shallowest.
    3.  It processes these packages in batches according to their depth. For each package, it gathers the summaries of its direct children (sub-packages or types) from the cache.
    4.  This context is used to generate a summary for the parent package.
-   **Rationale**: The strict bottom-up ordering guarantees that when summarizing a package like `com.myproject`, the summaries for `com.myproject.utils` and `com.myproject.api` are already available.

### Phase 2: Summarize ClassTree Roots

-   **What**: Generates summaries for the root `:ClassTree` nodes themselves (e.g., JAR files or validated package-structure roots like `target/classes`).
-   **How**:
    1.  After Phase 1 is complete, it executes a second query to find all `:ClassTree` nodes.
    2.  For each `:ClassTree`, it gathers the summaries of its direct children (the top-level packages that were just summarized in Phase 1).
    3.  This context is used to generate a final, top-level summary for the entire JAR or class directory.
-   **Rationale**: This final step provides a high-level overview of each major component or dependency.

## 3. Key Logic

-   **Querying**: The summarizer uses two distinct queries to implement its two-phase approach.
-   **Context Gathering**: It relies exclusively on the clean `[:CONTAINS_CLASS]` relationship to find child nodes.
-   **Skip Logic**: The queries explicitly exclude any node that already has a `summary` property (`WHERE p.summary IS NULL`). This is a critical feature that allows it to work alongside the `DirectorySummarizer`. If a directory is both a `:ClassTree` and part of the source tree, the `DirectorySummarizer` runs first and creates a summary. The `PackageSummarizer` will then safely skip it, prioritizing the source code-based summary.

## 4. Dependencies

-   `base_summarizer.BaseSummarizer`: Inherits the common summarization processing logic.
-   `node_summary_processor.NodeSummaryProcessor`: To handle the actual LLM call and context management.
-   `neo4j_manager.Neo4jManager`: To query for nodes and write back the generated summaries.
