import logging
import os
from typing import List, Dict, Any
from tqdm import tqdm

from neo4j_manager import Neo4jManager # Import the new Neo4jManager

logger = logging.getLogger(__name__)

class GraphEnricher: # Renamed class
    """
    Enriches the jQAssistant graph by connecting :File nodes to :Type:Class nodes
    via a [:WITH_SOURCE] relationship.
    """
    def __init__(self, neo4j_manager: Neo4jManager): # Accepts Neo4jManager instance
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized GraphEnricher.")

    # Removed __enter__ and __exit__ as Neo4jManager handles driver management

    def enrich_graph(self, source_metadata: List[Dict[str, Any]]):
        """
        Enriches the graph by connecting :File nodes to :Type:Class nodes
        via a [:WITH_SOURCE] relationship.
        """
        if not source_metadata:
            logger.warning("No source metadata provided for enrichment. Skipping.")
            return 0

        logger.info(f"Starting graph enrichment for {len(source_metadata)} source files.")
        
        # The Cypher query to create relationships in batches
        # It matches the File node by its fileName (relative path)
        # Then, for each FQN in the file_data, it matches the Type:Class node by its fqn property
        # Finally, it MERGEs the [:WITH_SOURCE] relationship (reversed direction)
        cypher_query = """
        UNWIND $metadata AS file_data
        MATCH (file:File {fileName: file_data.path})
        UNWIND file_data.fqns AS class_fqn
        MATCH (class:Type:Class {fqn: class_fqn})
        MERGE (class)-[r:WITH_SOURCE]->(file)
        RETURN count(r) AS relationships_created
        """
        total_relationships_created = 0
        batch_size = 1000 # Process 1000 files at a time

        # Use the injected neo4j_manager for session and query execution
        with self.neo4j_manager._driver.session() as session: # Access driver from manager
            for i in tqdm(range(0, len(source_metadata), batch_size), desc="Enriching Neo4j graph"):
                batch = source_metadata[i:i + batch_size]
                if True:
                    if batch[0]['path'] == '/jadx-gui/src/main/java/jadx/gui/plugins/quark/QuarkReportPanel.java':
                        if batch[0]['fqns'][0] == 'jadx.gui.plugins.quark.QuarkReportPanel' :
                            logger.info(f"{batch[0]['path']} ==> {batch[0]['fqns']}")
                try:
                    # Use execute_write_query for MERGE operations
                    summary = self.neo4j_manager.execute_write_query(cypher_query, params={"metadata": batch})
                    relationships_created_in_batch = summary.relationships_created
                    total_relationships_created += relationships_created_in_batch
                except Exception as e:
                    logger.error(f"Error enriching graph with batch starting at index {i}: {e}")
        
        logger.info(f"Graph enrichment complete. Total new [:WITH_SOURCE] relationships created: {total_relationships_created}.")
        return total_relationships_created
