# Plan: 050 - Type Summaries (Class, Interface, Enum, Record)

## 1. Goal

This pass focuses on generating `summary` properties for `:Type` nodes. The summarization will incorporate information from their contained `:Method` nodes (from Pass 040) and their parent types/interfaces.

## 2. Rationale

*   **Structural Understanding**: Type summaries provide a high-level understanding of the purpose and functionality of core code structures.
*   **Foundation for File/Package Summaries**: These summaries are crucial for rolling up to higher-level entities like source files and packages.
*   **Hierarchical Context**: Summarizing in dependency order (base types before derived types) ensures that summaries of derived types can leverage the context of their base types. (Note: The implementation handles this via level-by-level processing).
*   **Rolling-Up Logic**: A Type node will only receive a summary if it has summarized methods or parent types. This ensures summaries are built from available context.
*   **Neo4j `id()` Deprecation**: All queries use `elementId()` for node identification, ensuring compatibility with Neo4j 5.x.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve type details, method summaries, and parent type summaries.
*   LLM calls (simulated for now) to generate `summary` properties.

### Step 3.1: Retrieve Type Details and Context

*   **Logic**: Find `:Type` nodes. For each, gather:
    *   Its `fqn` and `name`.
    *   Its `absolute_path` from its associated `:SourceFile` (via `[:WITH_SOURCE]`).
    *   The `summary` properties of its directly declared `:Method` nodes (from Pass 040).
    *   The `summary` properties of its parent `:Type` nodes (via `[:EXTENDS]` or `[:IMPLEMENTS]`).
    *   This step now correctly handles all `:Type` nodes, including external ones (e.g., `java.lang.Object`) that might not have specific labels like `:Class`, `:Interface`, etc., by matching on the generic `:Type` label.
*   **Cypher**:
    ```cypher
    MATCH (t:Type)
    WHERE elementId(t) = $typeId
    OPTIONAL MATCH (t)-[:DECLARES]->(m:Method)
    WHERE m.summary IS NOT NULL
    OPTIONAL MATCH (t)-[:EXTENDS|IMPLEMENTS]->(p:Type)
    WHERE p.summary IS NOT NULL
    OPTIONAL MATCH (t)-[:WITH_SOURCE]->(sf:SourceFile)
    RETURN sf.absolute_path AS sourceFilePath,
           COLLECT(DISTINCT {methodName: m.name, methodSummary: m.summary}) AS methodSummaries,
           COLLECT(DISTINCT {parentFqn: p.fqn, parentSummary: p.summary}) AS parentSummaries
    ```

### Step 3.2: Generate `summary` for Types

*   **Logic**: For each `:Type` node:
    1.  Combine the retrieved context (source file path, method summaries, parent summaries).
    2.  If the combined context is empty (meaning no summarized methods or parent types), skip summary generation.
    3.  Otherwise, send this combined context to an LLM (simulated) with a prompt asking for a concise summary of the type's purpose and functionality.
    4.  Store the result in `t.summary`.
*   **LLM Prompt Example (simulated)**: "Based on the following source file, method summaries, and parent type summaries, provide a concise summary of this {type_label}'s purpose and functionality."
*   **Implementation**: Handled by `_generate_type_summary` in `CodeAnalyzer`.

### Step 3.3: Update Neo4j Graph

*   **Logic**: Batch update the `:Type` nodes with the newly generated `summary` properties.
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $updates AS item
    MATCH (t:Type)
    WHERE elementId(t) = item.typeId
    SET t.summary = item.summary
    ```

## 4. Expected Outcome

*   `:Type` nodes (including `:Class`, `:Interface`, `:Enum`, and `:Record`) will have a `summary` property, provided they have summarized children or parent types.
*   These summaries will incorporate information from their methods and parent types, providing a contextual understanding of each type.
*   These summaries will be used in subsequent passes for rolling up to source files and packages.