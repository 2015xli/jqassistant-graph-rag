# Plan: 050 - Type Summaries (Class, Interface, Enum)

## 1. Goal

This pass focuses on generating summaries for core `:Type` nodes, specifically `:Class`, `:Interface`, and `:Enum`. This pass will:

1.  Generate `summary` properties for these `:Type` nodes.
2.  Ensure summarization respects the inheritance and implementation hierarchy (summarize base types before derived types).
3.  Incorporate summaries from contained `:Method` nodes (from Pass 040) and the type's source code (via `[:WITH_SOURCE]`).

## 2. Rationale

*   **Structural Understanding**: Type summaries provide a high-level understanding of the purpose and functionality of core code structures.
*   **Foundation for File/Package Summaries**: These summaries are crucial for rolling up to higher-level entities like source files and packages.
*   **Hierarchical Context**: Summarizing in dependency order ensures that summaries of derived types can leverage the context of their base types.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve type source code and method summaries.
*   LLM calls to generate `summary` properties.

### Step 3.1: Determine Summarization Order (Dependency-Aware)

*   **Logic**: Summarize types in an order that respects their dependencies (e.g., base classes before derived classes, implemented interfaces before implementing classes). This can be achieved by finding types with no outgoing `[:EXTENDS]` or `[:IMPLEMENTS]` relationships first, then iteratively processing types whose dependencies have already been summarized.
*   **Cypher (Example for finding types by inheritance depth)**:
    ```cypher
    MATCH (t:Type)
    WHERE t:Class OR t:Interface OR t:Enum
    OPTIONAL MATCH (t)-[:EXTENDS|IMPLEMENTS]->(baseType:Type)
    WITH t, COUNT(baseType) AS numDependencies
    ORDER BY numDependencies ASC // Simple heuristic for bottom-up processing
    RETURN t.fqn AS fqn, labels(t) AS labels
    ```
    *   **Note**: A more robust approach might involve `apoc.algo.topologicalSort` or iterative processing based on a custom depth calculation.

### Step 3.2: Generate `summary` for Types

*   **Logic**: For each `:Type` node in the determined order:
    1.  Retrieve its source code (via `[:WITH_SOURCE]` to `:SourceFile`, then read the file content and extract the type's body).
    2.  Gather summaries (`summary` property) of its contained `:Method` nodes (from Pass 040).
    3.  Gather summaries (`summary` property) of its base types or implemented interfaces (from already processed types in this pass).
    4.  Send this combined context to an LLM with a prompt asking for a concise summary of the type's purpose and functionality. Store the result in `type.summary`.
*   **LLM Prompt Example**: "Based on the following source code, method summaries, and base type summaries, provide a concise summary of this {type_label}'s purpose and functionality."
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $types AS typeData
    MATCH (t:Type {fqn: typeData.fqn})
    SET t.summary = typeData.summary
    ```

## 4. Expected Outcome

*   `:Type:Class`, `:Type:Interface`, and `:Type:Enum` nodes will have a `summary` property.
*   These summaries will incorporate information from their methods and base types, providing a contextual understanding of each type.
*   These summaries will be used in subsequent passes for rolling up to source files and packages.
