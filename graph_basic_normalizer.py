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

        # Set absolute_path for top-level :Directory nodes, including both
        # Artifact:Directory nodes (scanned with java:classpath:: prefix) and
        # non-Artifact:Directory nodes (scanned directly as directories).
        # We need set the absolute_path for the top-level :Directory nodes themselves,
        # and also for the files and directories contained within them.
        # We jQAssistant scans a directory, the entry node is a :Directory node,
        # and its fileName property is the absolute path of the directory.
        # This entry node is the root of the directory tree.
        # It _directly_ :CONTAINS all of the :File and :Directory (also a :File) nodes in the tree.
        # The containership does not cross Artifact boundaries 
        # (i.e., the root node does not :CONTAINS the nodes under an :Artifact:Jar file node).
        # This makes it easy to find all the descendants of the root node by a single step :CONTAINS.
        # The fileName of the nodes within the directory tree is the relative path from the entry node.
        # So we need to concatenate the parent's absolute_path with the children nodes' fileName for the absolute_path of the children nodes.
        directory_tree_query = """
        MATCH (e:Directory)
        WHERE NOT EXISTS { (:Directory)-[:CONTAINS]->(e) }
        SET e.absolute_path = e.fileName
        WITH e
        MATCH (e)-[:CONTAINS]->(c:File)
        SET c.absolute_path = e.absolute_path + c.fileName
        RETURN count(e) + count(c) AS paths_normalized
        """
        dir_tree_result = self.neo4j_manager.execute_write_query(directory_tree_query)
        dir_tree_props_set = dir_tree_result.properties_set
        logger.info(
            f"Set 'absolute_path' for {dir_tree_props_set} Directory nodes and their contained files."
        )

        return dir_tree_props_set




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

        # 1.2. Second, set the path for the files and directories contained within them.
        # Since all the descendant nodes are contained directly by the Artifact:Directory nodes,
        # and the containership does not cross Artifact boundaries (to the nodes under an :Artifact:Jar node),
        # we can simply concatenate the parent's absolute_path with the children nodes' fileName.
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

        # Step 2: Set absolute_path for top-level non-Artifact:Directory nodes.
        # 2.1. If jQAssistant scans a directory without using java:classpath:: prefix,
        # User may scan a directory with source files only in this way.
        # In this case, the top-level nodes will be :Directory nodes, not Artifact:Directory nodes.
        non_artifact_query = """
        MATCH (e:Directory)
        WHERE e.fileName IS NOT NULL AND NOT e:Artifact
        SET e.absolute_path = e.fileName
        RETURN count(e) AS paths_normalized
        """
        non_artifact_result = self.neo4j_manager.execute_write_query(non_artifact_query)
        non_artifact_props_set = non_artifact_result.properties_set
        logger.info(
            f"Set 'absolute_path' for {non_artifact_props_set} top-level non-Artifact Directory nodes."
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
