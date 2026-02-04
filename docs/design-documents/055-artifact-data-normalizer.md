# Design: ArtifactDataNormalizer

## 1. Purpose and Role

The `ArtifactDataNormalizer` is a foundational and highly critical component that performs a fundamental refactoring of the raw jQAssistant graph. Its primary purpose is to correct deep structural inconsistencies that arise when jQAssistant scans a directory that is not a pure classpath root (e.g., a full project source tree).

It achieves this by executing a precise sequence of passes that:
1.  **De-duplicates** "phantom" nodes created by jQAssistant's dependency resolution.
2.  **Intelligently relocates** the misplaced `:Artifact` label from the top-level scanned directory to the true roots of compiled class hierarchies (e.g., `target/classes`).
3.  **Surgically rewrites** the graph's core `[:CONTAINS]` and `[:REQUIRES]` relationships to be consistent with the newly corrected artifact structure.
4.  **Builds** the clean `[:CONTAINS_CLASS]` overlay on top of this corrected structure, providing a simple, reliable hierarchy for summarizers and agents.

This component is the key to transforming an ambiguous, partially incorrect graph into an architecturally sound and reliable model of the project's components.

## 2. Workflow and Passes

The normalizer executes its passes in a strict, dependency-aware order. It maintains state between passes using a map (`relocated_artifacts_map`) to ensure efficiency and avoid redundant queries.

---

### Pass 1: `merge_duplicate_types()`

-   **What**: Finds and merges duplicate `:Type` and `:Member` nodes within each `:Directory:Artifact`.
-   **Problem**: jQAssistant creates two nodes for the same entity: a "real" node with complete properties when it parses a `.class` file (linked via `[:CONTAINS]`), and a "phantom" node with incomplete properties when it's referenced by another class (linked via `[:REQUIRES]`).
-   **How**: It runs two queries using the `apoc.refactor.mergeNodes` procedure:
    1.  **For Types**: It finds pairs of `:Type` nodes within the same artifact that share an `fqn`. It deterministically identifies the "real" node as the one with the longer `fileName` (the full relative path) and the "phantom" as the one with the shorter, derived `fileName`. It then merges the phantom into the real one.
    2.  **For Members**: It finds pairs of `:Member` nodes within the same `:Type` that share a `signature`. It identifies the "real" member as the one that has a `name` property and merges the phantom (which lacks a `name`) into it.
-   **Rationale**: This is a critical first cleanup step. It ensures that every logical type and member is represented by a single, complete node before any further structural changes are made.

---

### Pass 2: `relocate_directory_artifacts()`

-   **What**: Intelligently validates each scanned `:Directory:Artifact` and, only if it's incorrect, demotes it and promotes the true class hierarchy roots to be `:Artifact`s.
-   **How**: This pass uses a "validate-first" heuristic for each scanned directory artifact:
    1.  It finds a deeply nested "anchor" `:Class` file and uses its `fqn` to calculate the expected package path (e.g., `com.example.util` -> `/com/example/util`).
    2.  It compares this to the class's actual directory path within the artifact. It calculates the "base path" that precedes the package path.
    3.  **The Verdict**:
        -   If the `base_path` is empty, it proves the package structure starts at the root. The current `:Artifact` is **correct**, and no changes are made.
        -   If the `base_path` is not empty (e.g., `/target/classes`), it proves the `:Artifact` label is misplaced.
    4.  **Action (only if invalid)**: The pass demotes the current node (removes its `:Artifact` label) and promotes the correct sub-directory (identified by the `base_path`) to be the new, true `:Artifact`. It also updates the new artifact's `fileName` to be its `absolute_path`, conforming to jQAssistant conventions.
-   **State Management**: This pass populates the `relocated_artifacts_map`, recording which original artifacts were demoted and which new artifacts were promoted from within them. This state is crucial for the efficiency of subsequent passes.
-   **Rationale**: This intelligent approach avoids unnecessary graph mutations for correctly scanned artifacts and only acts when it has proven that a correction is needed.

---

### Pass 3: `rewrite_containment_relationships()`

-   **What**: Rewrites the graph's core `[:CONTAINS]` relationships to be consistent with the new `:Artifact` nodes.
-   **How**: This is a two-step operation:
    1.  **Addition**: For every true `:Artifact` (new and old), it creates the correct transitive `[:CONTAINS]` relationships to all of their descendant nodes by traversing the existing hierarchical `[:CONTAINS*]` links.
    2.  **Deletion**: Using the `relocated_artifacts_map`, it finds the demoted roots and carefully deletes their now-incorrect transitive `[:CONTAINS]` relationships. The query preserves the essential direct, parent-to-child links by comparing the `absolute_path` depth of the parent and child.
-   **Rationale**: This pass makes the graph's core structure behave exactly as if jQAssistant had scanned each artifact perfectly from the start.

---

### Pass 4: `rewrite_requirement_relationships()`

-   **What**: Relocates the `[:REQUIRES]` relationships from the demoted artifact roots to the newly promoted, correct `:Artifact` nodes.
-   **How**: This is also a two-step "relocation" operation that uses the `relocated_artifacts_map`:
    1.  **Addition**: It finds types that were required by a demoted root, identifies which new artifact contains the code that depends on those types, and creates a new `[:REQUIRES]` link from the new, correct artifact.
    2.  **Deletion**: It deletes all `[:REQUIRES]` relationships from all demoted roots.
-   **Rationale**: This ensures that high-level, artifact-to-type dependency information remains accurate after the artifact relocation.

---

### Pass 5: `establish_class_hierarchy()`

-   **What**: Builds the clean, parent-child `[:CONTAINS_CLASS]` relationship overlay.
-   **How**: After the core graph is corrected, this pass iterates through each true `:Artifact`. Within each artifact, it uses a bottom-up approach to build the simple, hierarchical `[:CONTAINS_CLASS]` overlay, using the corrected `[:CONTAINS]` relationship as a guardrail to prevent cross-artifact links.
-   **Rationale**: This provides the simple, unambiguous hierarchy that summarizers and agents need, separate from the more complex `[:CONTAINS]` relationship.

---

### Pass 6: `cleanup_package_semantics()` & `link_project_to_artifacts()`

-   **`cleanup_package_semantics`**: This pass removes the `:Package` label and `fqn` property from any directory that is not a validated member of the new `[:CONTAINS_CLASS]` hierarchy.
-   **`link_project_to_artifacts`**: This final pass creates the top-level `[:CONTAINS_CLASS]` link from the `:Project` node to every true `:Artifact`, making the class hierarchy easily discoverable.

## 3. Dependencies

-   `neo4j_manager.Neo4jManager`: To execute all Cypher queries.
-   APOC Library: The `apoc.refactor.mergeNodes` procedure is required for the `merge_duplicate_types` pass.
