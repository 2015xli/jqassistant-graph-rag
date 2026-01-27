import logging
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class GraphBasicNormalizer:
    """
    Handles the first phase of graph normalization: adding canonical path
    information and identifying source files.
    """

    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized GraphBasicNormalizer.")

    def add_absolute_paths(self):
        """
        Adds an 'absolute_path' property to all filesystem nodes, including
        the top-level artifacts themselves.
        """
        logger.info("--- Starting Pass: Add Absolute Paths ---")

        # First, set the absolute_path for the Artifact:Directory nodes themselves.
        artifact_query = """
        MATCH (e:Artifact&Directory)
        WHERE e.fileName IS NOT NULL
        SET e.absolute_path = e.fileName
        RETURN count(e) AS paths_normalized
        """
        artifact_result = self.neo4j_manager.execute_write_query(artifact_query)
        artifact_props_set = artifact_result.properties_set
        logger.info(
            f"Set 'absolute_path' for {artifact_props_set} Artifact:Directory nodes."
        )

        # Second, set the path for the files and directories contained within them.
        contained_query = """
        MATCH (e:Artifact&Directory)-[:CONTAINS]->(f:File|Directory)
        WHERE e.fileName IS NOT NULL AND f.fileName IS NOT NULL
        SET f.absolute_path = e.fileName + f.fileName
        RETURN count(f) AS paths_normalized
        """
        contained_result = self.neo4j_manager.execute_write_query(contained_query)
        contained_props_set = contained_result.properties_set
        logger.info(
            f"Set 'absolute_path' for {contained_props_set} contained File/Directory nodes."
        )
        logger.info("--- Finished Pass: Add Absolute Paths ---")

    def label_source_files(self):
        """
        Identifies and labels :File nodes that represent Java or Kotlin
        source code files as :SourceFile.
        This pass relies on 'absolute_path' having been set previously.
        """
        logger.info("--- Starting Pass: Label Source Files ---")
        query = """
        MATCH (f:File)
        WHERE f.absolute_path IS NOT NULL
        AND (f.absolute_path ENDS WITH '.java' OR f.absolute_path ENDS WITH '.kt')
        SET f:SourceFile
        RETURN count(f) AS source_files_labeled
        """
        result = self.neo4j_manager.execute_write_query(query)
        labels_added = result.labels_added
        logger.info(f"Labeled {labels_added} files as :SourceFile.")
        logger.info("--- Finished Pass: Label Source Files ---")
