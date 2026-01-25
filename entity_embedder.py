import logging
from neo4j_manager import Neo4jManager
from llm_client import EmbeddingClient

logger = logging.getLogger(__name__)


class EntityEmbedder:
    """
    Generates summaryEmbeddings for all :Entity nodes that have a summary
    and ensures a vector index exists for querying.
    """

    def __init__(
        self, neo4j_manager: Neo4jManager, embedding_client: EmbeddingClient
    ):
        self.neo4j_manager = neo4j_manager
        self.embedding_client = embedding_client
        logger.info("Initialized EntityEmbedder.")

    def add_entity_labels_and_embeddings(self):
        """
        Generates summaryEmbeddings for all summarized :Entity nodes and
        creates a vector index.
        """
        logger.info("--- Starting Pass: EntityEmbedder ---")

        # Step 1: Generate summaryEmbedding for summarized :Entity nodes
        logger.info("Generating summaryEmbeddings for :Entity nodes...")
        batch_size = 500  # Configurable batch size
        skip = 0
        total_embeddings_generated = 0

        while True:
            # Fetch a batch of nodes that have a summary but no embedding yet
            nodes_to_embed = self.neo4j_manager.execute_read_query(
                """
                MATCH (e:Entity)
                WHERE e.summary IS NOT NULL
                RETURN e.entity_id AS id, e.summary AS summary
                SKIP $skip LIMIT $limit
                """,
                params={"skip": skip, "limit": batch_size},
            )
            skip += batch_size
            if not nodes_to_embed:
                break  # Exit loop if no more nodes to process
        
            node_ids = [record["id"] for record in nodes_to_embed]
            node_summaries = [record["summary"] for record in nodes_to_embed]

            logger.info(
                f"Processing batch of {len(node_summaries)} nodes for embedding..."
            )
            embeddings = self.embedding_client.generate_embeddings(
                node_summaries
            )

            updates = [
                {"id": node_id, "embedding": emb}
                for node_id, emb in zip(node_ids, embeddings)
            ]

            # Update the embeddings for the current batch in the database
            self.neo4j_manager.execute_write_query(
                """
                UNWIND $updates AS item
                MATCH (e:Entity {entity_id: item.id})
                SET e.summaryEmbedding = item.embedding
                """,
                params={"updates": updates},
            )

            total_embeddings_generated += len(updates)
            # We don't need to increment skip, as the next query will
            # naturally find the next batch of nodes without embeddings.

        logger.info(
            "Embedding generation complete. Generated or updated "
            f"{total_embeddings_generated} embeddings."
        )

        # Step 2: Create Vector Index
        logger.info("Creating/updating vector index 'summary_embeddings'...")
        self.neo4j_manager.execute_write_query(
            """
            CREATE VECTOR INDEX summary_embeddings IF NOT EXISTS
            FOR (e:Entity) ON (e.summaryEmbedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 384,
                `vector.similarity_function`: 'cosine'
            }}
            """
        )
        logger.info("Vector index 'summary_embeddings' is ready.")
        logger.info("--- Pass: EntityEmbedder Complete ---")
