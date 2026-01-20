# Plan: 080 - Package Summaries

## 1. Goal

This pass focuses on generating summaries for `:Package` nodes. As per schema analysis, jQAssistant represents packages as `:Package:Directory` nodes. This pass will:

1.  Generate `summary` properties for `:Package` nodes.
2.  Incorporate summaries from the `:Type` nodes (Class, Interface, Enum) that belong to that package (from Pass 050).
3.  Clarify the distinction between `:Package` and other `:Directory` nodes in the context of summarization.

## 2. Rationale

*   **Logical Grouping**: Package summaries provide an understanding of the logical organization and functionality of code within a package.
*   **Dual-Track Analysis**: This pass contributes to the package-centric analysis track, complementing the file system-centric directory summaries.
*   **Agent Navigation**: Allows an AI agent to quickly grasp the purpose of a package.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to traverse the graph and retrieve summaries of contained types.
*   LLM calls to generate `summary` properties.

### Step 3.1: Retrieve Package Context (Summaries of Contained Types)

*   **Logic**: Find `:Package` nodes. For each `:Package` node, find all `:Type` nodes that it contains (via `[:CONTAINS]` relationship from `Package` to `Type`) and retrieve their `summary` properties (generated in Pass 050).
*   **Cypher (to get package and its contained type summaries)**:
    ```cypher
    MATCH (p:Package)-[:CONTAINS]->(type:Type)
    WHERE type.summary IS NOT NULL
    RETURN p.fqn AS packageFqn, COLLECT(type.summary) AS containedTypeSummaries
    LIMIT 1000 // Process in batches
    ```
    *   **Note**: Based on schema analysis, jQAssistant uses `[:CONTAINS]` from `Package` to `Type`.

### Step 3.2: Generate `summary` for Packages

*   **Logic**: For each `:Package` node:
    1.  Combine the `containedTypeSummaries` (from Step 3.1).
    2.  Send this combined context to an LLM with a prompt asking for a concise summary of the package's overall purpose and contents. Store the result in `p.summary`.
*   **LLM Prompt Example**: "Based on the following summaries of types contained within this package, provide a concise summary of the package's overall purpose and functionality."
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $packages AS packageData
    MATCH (p:Package {fqn: packageData.packageFqn})
    SET p.summary = packageData.summary
    ```

### Step 3.3: Clarify Distinction between `:Package` and `:Directory`

*   **Logic**: As noted by the user, jQAssistant's schema can be confusing. A `:Directory` node might also represent a package. We need to ensure our summarization process handles this without double-counting or creating conflicting summaries.
*   **Suggestion**: The summarization passes are distinct. `:Directory` summaries are based on physical file system hierarchy (`[:CONTAINS_DIRECT]`), while `:Package` summaries are based on logical grouping of types (`[:CONTAINS]` from `Package` to `Type`). The `main.py` orchestrator will ensure these passes run independently. If a node has both `:Directory` and `:Package` labels, it will receive two distinct summaries (one as a directory, one as a package), which is acceptable as they represent different facets.

## 4. Expected Outcome

*   `:Package` nodes will have a `summary` property.
*   These summaries will reflect the logical grouping and functionality of types within the package.
*   These summaries will be used in subsequent passes for rolling up to the project node.
