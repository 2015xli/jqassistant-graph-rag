import logging
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class GraphEntitySetter:
    """
    Handles the final phase of graph normalization: labeling all relevant nodes
    as :Entity and assigning them a stable, unique entity_id.
    """

    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized GraphEntitySetter.")

    def create_entities_and_stable_ids(self):
        """
        Creates a stable, unique 'entity_id' for all relevant nodes and
        labels them as :Entity. This pass is critical for caching and
        dependency tracking.
        """
        logger.info("--- Starting Pass: Create Entities and Stable IDs ---")

        # 1. Create uniqueness constraint
        self.neo4j_manager.execute_write_query(
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE"
        )
        logger.info("Ensured :Entity(entity_id) uniqueness constraint exists.")

        # 2. Generate entity_id for :Project
        self.neo4j_manager.execute_write_query(
            """
            MATCH (p:Project)
            SET p:Entity, p.entity_id = apoc.util.md5(["Project://", p.absolute_path])
            """
        )
        logger.info("Generated entity_id for :Project node.")

        # 3. Generate entity_id for :Artifact
        self.neo4j_manager.execute_write_query(
            """
            MATCH (a:Artifact)
            WHERE a.fileName IS NOT NULL
            SET a:Entity, a.entity_id = apoc.util.md5([a.fileName])
            """
        )
        logger.info("Generated entity_id for :Artifact nodes.")

        # 4. Generate entity_id for file-system-like nodes
        self.neo4j_manager.execute_write_query(
            """
            MATCH (a:Artifact)-[:CONTAINS]->(n)
            WHERE (n:File OR n:Directory OR n:Package OR n:Type)
            AND n.fileName IS NOT NULL AND a.fileName IS NOT NULL
            SET n:Entity, n.entity_id = apoc.util.md5([a.fileName, n.fileName])
            """
        )
        logger.info("Generated entity_id for file-system-like nodes.")

        # 5. Generate entity_id for :Member nodes
        self.neo4j_manager.execute_write_query(
            """
            MATCH (a:Artifact)-[:CONTAINS]->(t:Type)-[:DECLARES]->(m:Member)
            WHERE t.fileName IS NOT NULL AND m.signature IS NOT NULL AND a.fileName IS NOT NULL
            SET m:Entity, m.entity_id = apoc.util.md5([a.fileName, t.fileName, m.signature])
            """
        )
        logger.info("Generated entity_id for :Member nodes.")
        logger.info("--- Finished Pass: Create Entities and Stable IDs ---")
