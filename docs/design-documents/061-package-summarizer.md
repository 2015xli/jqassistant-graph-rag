# Design: PackageSummarizer

## 1. Purpose and Role

The `PackageSummarizer` is a hierarchical summarizer responsible for generating summaries for the logical package structure of the project. It operates on the clean, validated `[:CONTAINS_CLASS]` hierarchy that originates from the corrected `:Artifact` nodes.

Its goal is to "roll up" information from individual types to provide a high-level overview of what each package and dependency artifact (e.g., JAR file) contributes to the project.

## 2. Workflow

The `PackageSummarizer` uses a robust, two-phase, bottom-up approach.

### Phase 1: Summarize Internal Packages

-   **What**: Generates summaries for all the individual `:Package` nodes that are nested inside an `:Artifact` container.
-   **How**: It executes a query to find all `:Package` nodes descending from an `:Artifact` via `[:CONTAINS_CLASS*]`, ordering them from deepest to shallowest based on their `fqn` depth. This ensures child packages are always processed before their parents.

### Phase 2: Summarize Artifact Roots

-   **What**: Generates summaries for the root `:Artifact` nodes themselves (e.g., JAR files or validated class directories like `target/classes`).
-   **How**: After Phase 1 is complete, it executes a second query to find all `:Artifact` nodes. For each one, it gathers the summaries of its direct children (the top-level packages just summarized) to generate a final, top-level summary for the entire artifact.

## 3. Key Logic

-   **Querying**: The summarizer uses two distinct queries to implement its two-phase, bottom-up approach.
-   **Context Gathering**: It relies exclusively on the clean `[:CONTAINS_CLASS]` relationship.
-   **Skip Logic**: The queries explicitly exclude any node that already has a `summary` property, allowing it to safely cede priority to the `DirectorySummarizer` if a node represents both source and classes.

## 4. Dependencies

-   `base_summarizer.BaseSummarizer`: Inherits the common summarization processing logic.
-   `node_summary_processor.NodeSummaryProcessor`: To handle the actual LLM call and context management.
-   `neo4j_manager.Neo4jManager`: To query for nodes and write back the generated summaries.
