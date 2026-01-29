# Design: PackageDataNormalizer

## 1. Purpose and Role

The `PackageDataNormalizer` is a critical enrichment component responsible for making sense of the often-ambiguous package structures within a jQAssistant graph. Its primary goal is to identify reliable package hierarchies, correct the `fqn` (Fully Qualified Name) properties on package directories, and build a clean, traversable `[:CONTAINS_CLASS]` hierarchy overlay.

This component creates a clear distinction between the physical source tree (`[:CONTAINS_SOURCE]`) and the logical package/dependency tree (`[:CONTAINS_CLASS]`), which is essential for accurate hierarchical summarization.

## 2. Workflow and Passes

The normalizer executes its passes in a specific, dependency-aware order.

### Pass: `label_jar_artifacts_as_class_trees()`

-   **What**: Identifies known-good package hierarchies.
-   **How**: Finds all `:Jar:Artifact` nodes and applies a `:ClassTree` label to them.
-   **Rationale**: JAR files have a mandated, reliable package structure. Labeling them as `:ClassTree` provides a trusted baseline.

### Pass: `normalize_directory_packages()`

-   **What**: Finds and validates potential package structures within generic `:Directory:Artifact` containers.
-   **How**: This pass uses a sophisticated "anchor and validate" heuristic. For each artifact, it iteratively:
    1.  Finds the `:Class` file with the longest `fqn` to use as an anchor.
    2.  Uses the class's correct `fqn` to infer the expected directory path for its package.
    3.  Validates that the actual directory structure matches the expected package path.
    4.  If valid, it labels the root of this structure as a `:ClassTree` and runs a sub-pass to correct the `fqn` properties of all directories within that tree.
-   **Rationale**: This surgically corrects package information where possible without making unsafe assumptions about directory structures that don't contain class files.

### Pass: `establish_class_hierarchy()`

-   **What**: Builds the clean, parent-child `[:CONTAINS_CLASS]` relationship overlay, ensuring artifact boundaries are respected.
-   **How**: This pass iterates through each `:ClassTree` node individually. For each tree, it performs a bottom-up traversal, creating `[:CONTAINS_CLASS]` relationships between parent directories and their direct children (sub-directories and `:Type` files). To prevent incorrect links between different artifacts that might share package names (e.g., two JARs both containing `org.apache`), the query uses the existing, reliable `[:CONTAINS]` relationship as a guardrail, ensuring a parent and child are part of the same original artifact before linking them.
-   **Rationale**: This robust, per-artifact approach prevents the "cross-boundary" problem and guarantees that the resulting `[:CONTAINS_CLASS]` hierarchy is a true and accurate representation of each individual component's structure. It mirrors the logic of the `[:CONTAINS_SOURCE]` tree.

### Pass: `cleanup_fqn_properties()`

-   **What**: Removes the `fqn` property from all directories that are not part of a validated package structure.
-   **How**: It runs a single Cypher query that finds any `:Directory` with an `fqn` that does *not* have an incoming `[:CONTAINS_CLASS]` relationship and removes the property.
-   **Rationale**: This final cleanup ensures that the `fqn` property is only present where it is semantically correct. It correctly removes the `fqn` from non-package directories as well as from the `:ClassTree` roots themselves (which are containers, not packages).

### Pass: `link_project_to_class_trees()`

-   **What**: Connects the single `:Project` node to the roots of all identified class hierarchies.
-   **How**: Creates a `[:CONTAINS_CLASS]` relationship from the `:Project` node to every node labeled `:ClassTree`.
-   **Rationale**: This establishes the top-level entry points for traversing the package and dependency graph.

## 3. Dependencies

-   `neo4j_manager.Neo4jManager`: To execute all Cypher queries.
