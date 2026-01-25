# Plan: 110 - Add `:Entity` Label and Generate Embeddings

## 1. Goal

This pass is crucial for enabling efficient semantic search across the entire graph. It standardizes the search interface for AI agents by providing a single entry point for vector similarity queries. This pass will:

1.  Add a generic `:Entity` label to all nodes that have a `summary` property.
2.  Generate `summaryEmbedding` (vector embeddings) for all nodes that have a `summary` property.
3.  Create a single, unified vector index on the `summaryEmbedding` property for all `:Entity` nodes.

## 2. Rationale

*   **Simplified Agent Search**: Instead of requiring the AI agent to know and query multiple label-specific vector indexes, it can now query a single `summary_embeddings` index on the `:Entity` label.
*   **Universal Identification**: Using Neo4j's `elementId()` for processing ensures that every node can be uniquely identified and updated, even without a universal custom ID property, and is compatible with Neo4j 5.x.
*   **Performance**: A single, well-maintained vector index can be more efficient for broad semantic searches.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to add labels and properties.
*   LLM calls (or local embedding model calls) to generate embeddings.
*   Cypher queries to create the vector index.

### Step 3.1: Add `:Entity` Label to Summarized Nodes

*   **Logic**: Find all nodes that have a `summary` property (meaning they have been summarized in previous passes) and add the `:Entity` label to them.
*   **Cypher**:
    ```cypher
    MATCH (n)
    WHERE n.summary IS NOT NULL
    SET n:Entity
    RETURN count(n) AS entitiesLabeled
    ```

### Step 3.2: Generate `summaryEmbedding` for Summarized Nodes

*   **Logic**: For each node that now has a `summary` property and the `:Entity` label, generate a vector embedding from its `summary` text. Store this vector in a new `summaryEmbedding` property.
*   **Cypher (to retrieve nodes for embedding)**:
    ```cypher
    MATCH (e:Entity)
    WHERE e.summary IS NOT NULL AND e.summaryEmbedding IS NULL
    RETURN elementId(e) AS nodeId, e.summary AS nodeSummary
    LIMIT 1000 // Process in batches
    ```
*   **LLM Call**: Send `nodeSummary` to the embedding model to get the vector.
*   **Cypher (to update `summaryEmbedding`)**:
    ```cypher
    UNWIND $nodes AS nodeData
    MATCH (e:Entity)
    WHERE elementId(e) = nodeData.nodeId
    SET e.summaryEmbedding = nodeData.embedding
    ```

### Step 3.3: Create Unified Vector Index

*   **Logic**: Create a vector index on the `summaryEmbedding` property for all `:Entity` nodes. This index will be named `summary_embeddings`.
*   **Cypher**:
    ```cypher
    CREATE VECTOR INDEX summary_embeddings IF NOT EXISTS FOR (e:Entity) ON (e.summaryEmbedding) OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
    ```
    *   **Note**: The `vector.dimensions` (e.g., 384) should match the output dimension of the embedding model used.

## 4. Expected Outcome

*   All summarized nodes will have the `:Entity` label.
*   All summarized nodes will have a `summaryEmbedding` property containing their vector representation.
*   A unified `summary_embeddings` vector index will exist, enabling efficient semantic search across the entire graph.
