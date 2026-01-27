# Design: EntityEmbedder

## 1. Purpose and Role

The `EntityEmbedder` is the final and culminating component in the RAG (Retrieval-Augmented Generation) pipeline. Its primary responsibility is to transform the textual, AI-generated summaries stored in the graph into numerical vector representations (embeddings). It then stores these embeddings back into the graph and ensures a vector index is available for them.

This process is what enables the "Retrieval" part of RAG. The vector embeddings allow for efficient semantic similarity searches, making it possible to find relevant code components based on a natural language query, rather than just keyword matching.

## 2. Workflow

The `EntityEmbedder` operates in a straightforward, two-step process, executed by its main `add_entity_labels_and_embeddings` method.

### Step 1: Embedding Generation

1.  **Batch Processing**: The component processes nodes in batches to manage memory usage and provide incremental updates.
2.  **Node Selection**: In a loop, it executes a Cypher query to fetch a batch of `:Entity` nodes that have a `summary` property but do not yet have a `summaryEmbedding` property.
3.  **Embedding Creation**: The list of summary texts from the batch is passed to the `EmbeddingClient`. The client (e.g., a local `SentenceTransformer` model) converts these texts into high-dimensional floating-point vectors.
4.  **Database Update**: The component executes a write query to update the graph, setting the `summaryEmbedding` property for each node in the batch with its newly generated vector.
5.  **Looping**: This process repeats until the selection query returns no more nodes, ensuring all summarized entities are eventually embedded.

### Step 2: Vector Index Creation

1.  **Index Management**: After the embedding generation loop is complete, the component executes a final Cypher query: `CREATE VECTOR INDEX summary_embeddings IF NOT EXISTS...`.
2.  **Idempotency**: This query is idempotent; it will only create the index if it doesn't already exist. This ensures that the necessary index for performing similarity searches on the `summaryEmbedding` property is always available. The index configuration (like vector dimensions and similarity function) is also defined here.

## 3. Key Methods

-   `__init__(self, neo4j_manager, embedding_client)`: The constructor takes a `Neo4jManager` for database interaction and an `EmbeddingClient` to perform the embedding generation.
-   `add_entity_labels_and_embeddings()`: The main public method that orchestrates the entire workflow of embedding generation and index creation.

## 4. Dependencies

-   `neo4j_manager.Neo4jManager`: To read nodes that need embedding, write the embedding vectors back to the graph, and create the vector index.
-   `llm_client.EmbeddingClient`: An abstraction for an embedding model. The concrete implementation (e.g., `SentenceTransformerClient`) performs the actual text-to-vector conversion.

## 5. Design Rationale

-   **Decoupling from Summarization**: The embedding process is a distinct step that runs *after* all summarization is complete. This is a clean separation of concerns. The summarization pipeline is focused on generating high-quality text, while the `EntityEmbedder` is focused on converting that text into a searchable format.
-   **Batch Processing**: Generating embeddings for thousands of nodes can be memory-intensive. Processing nodes in batches prevents loading all summaries into memory at once and makes the process more resilient.
-   **Idempotent and Re-runnable**: The entire process is designed to be re-runnable. On a subsequent run, it will only find and process nodes that are missing an embedding, making it efficient to update the graph after new summaries have been added. The index creation command is also idempotent, so it can be run safely every time.
-   **Abstraction of Embedding Model**: The component depends on the abstract `EmbeddingClient`, not a concrete implementation. This makes it easy to swap out the embedding model in the future (e.g., to switch from a local `SentenceTransformer` to a cloud-based embedding API) by simply changing the implementation passed to the constructor in the `RagOrchestrator`.
