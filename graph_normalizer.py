import logging
import os
from typing import List, Dict, Any
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

class GraphNormalizer:
    """
    Handles normalization of paths and establishment of a consistent project root
    within the jQAssistant graph.
    """
    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized GraphNormalizer.")

    def normalize_paths_and_project_root(self, project_name: str, project_path_arg: str):
        """
        Implements Pass 010:
        1. Creates a single :Project node.
        2. Identifies and labels :Artifact nodes as :Entry points.
        3. Adds 'relative_path' property to Directory/File nodes under :Entry:Directory.
        """
        logger.info("\n--- Starting Pass 010: Normalize Paths and Establish Project Root ---")

        # Step 3.1: Create the :Project Node
        self._create_project_node(project_name)

        # Step 3.2: Identify and Label :Entry Nodes (from :Artifact nodes)
        self._identify_and_label_entry_nodes(project_name)

        # Step 3.3: Add 'relative_path' Property for Directory and File Nodes under :Entry:Directory
        self._add_relative_path_to_filesystem_nodes()

        logger.info("--- Finished Pass 010 ---")

    def _create_project_node(self, project_name: str):
        """Creates a single :Project node."""
        query = """
        MERGE (p:Project {name: $projectName})
        ON CREATE SET p.creationTimestamp = datetime()
        RETURN p
        """
        result = self.neo4j_manager.execute_write_query(query, params={"projectName": project_name})
        logger.info(f"Created/Ensured :Project node '{project_name}'.")

    def _identify_and_label_entry_nodes(self, project_name: str):
        """Identifies :Artifact nodes as :Entry points and links them to the :Project node."""
        query = """
        MATCH (a:Artifact)
        SET a:Entry // Label all Artifacts as Entry points
        WITH a
        MATCH (p:Project {name: $projectName})
        MERGE (p)-[:CONTAINS_ENTRY]->(a) // Link to the Project node
        RETURN count(a) AS entryNodesCreated
        """
        result = self.neo4j_manager.execute_write_query(query, params={"projectName": project_name})
        logger.info(f"Labeled {result.nodes_created} :Artifact nodes as :Entry points and linked them to :Project.")

    def _add_relative_path_to_filesystem_nodes(self):
        """
        Adds 'relative_path' property to Directory and File nodes
        contained within an :Entry:Directory (non-JAR project root).
        """
        query = """
        MATCH (entry:Entry:Directory)-[:CONTAINS*]->(n) // Find all descendants of an Entry Directory
        WHERE (n:File OR n:Directory) AND n.fileName IS NOT NULL
        AND NOT n:Artifact // Exclude Artifacts themselves from getting relative_path if they are also File/Directory
        WITH n, entry
        // Calculate relative path: strip entry's absolute path from node's absolute path
        // Ensure leading '/' is removed if present in the result
        SET n.relative_path = CASE
                                WHEN n.fileName STARTS WITH entry.fileName THEN
                                    // Strip entry.fileName and then strip leading '/' if present
                                    substring(n.fileName, size(entry.fileName))
                                ELSE n.fileName // Fallback, though should not happen for descendants
                              END
        SET n.relative_path = CASE
                                WHEN n.relative_path STARTS WITH '/' THEN substring(n.relative_path, 1)
                                ELSE n.relative_path
                              END
        RETURN count(n) AS pathsNormalized
        """
        result = self.neo4j_manager.execute_write_query(query)
        logger.info(f"Normalized paths for {result.properties_set} Directory/File nodes under :Entry:Directory.")
