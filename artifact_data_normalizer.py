import logging
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


import logging
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class ArtifactDataNormalizer:
    """
    Handles the normalization of Artifact-related data in the graph.
    This includes relocating the :Artifact label from incorrectly scanned
    directories to the true roots of package/class hierarchies.
    """

    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized ArtifactDataNormalizer.")

    def relocate_directory_artifacts(self):
        """
        Finds incorrectly labeled Directory:Artifacts, demotes them, and promotes
        the true roots of class hierarchies within them to be :Artifacts.
        """
        logger.info("--- Starting Pass: Relocate Directory Artifacts ---")
        
        artifacts = self.neo4j_manager.execute_read_query(
            "MATCH (a:Directory:Artifact) RETURN a.fileName AS fileName"
        )
        artifact_files = [record['fileName'] for record in artifacts]

        for artifact_fileName in artifact_files:
            self._process_single_directory_artifact(artifact_fileName)
        
        logger.info("--- Finished Pass: Relocate Directory Artifacts ---")

    def _process_single_directory_artifact(self, artifact_fileName: str):
        """Helper to process one directory artifact at a time."""
        logger.info(f"Processing potential artifact container: {artifact_fileName}")
        
        # First, demote the top-level scanned directory.
        self.neo4j_manager.execute_write_query(
            "MATCH (a:Directory {fileName: $fileName}) WHERE a:Artifact REMOVE a:Artifact",
            params={"fileName": artifact_fileName}
        )

        query = """
        MATCH (cont:Directory {fileName: $artifact_fileName})-[:CONTAINS]->(c:File:Class)
        WHERE c.fqn IS NOT NULL AND c.fileName IS NOT NULL
        RETURN c.fqn AS fqn, c.fileName AS path
        """
        class_files = self.neo4j_manager.execute_read_query(query, params={"artifact_fileName": artifact_fileName})

        if not class_files:
            logger.info(f"No class files found in {artifact_fileName}. No new artifacts promoted.")
            return

        unprocessed_classes = {c['fqn']: c['path'] for c in class_files}
        
        while unprocessed_classes:
            anchor_fqn = max(unprocessed_classes.keys(), key=len)
            anchor_path = unprocessed_classes[anchor_fqn]

            package_parts = anchor_fqn.split('.')[:-1]
            package_as_path = "/" + "/".join(package_parts) if package_parts else ""

            anchor_dir = "/".join(anchor_path.split('/')[:-1])

            if not anchor_dir.endswith(package_as_path):
                del unprocessed_classes[anchor_fqn]
                continue

            artifact_root_path = anchor_dir[:-len(package_as_path)] if package_as_path else anchor_dir
            
            # Promote the validated root to a true :Artifact
            self.neo4j_manager.execute_write_query(
                """
                MATCH (cont:Directory {fileName: $artifact_fileName})-[:CONTAINS]->(d:Directory {fileName: $root_path})
                SET d:Artifact, d.fileName = d.absolute_path
                """,
                params={"artifact_fileName": artifact_fileName, "root_path": artifact_root_path}
            )
            logger.info(f"Promoted '{artifact_fileName}/{artifact_root_path}' to be a new :Artifact.")

            # Correct FQNs for all directories in this new Artifact's hierarchy
            self._correct_fqns_in_subtree(artifact_fileName, artifact_root_path)

            processed_in_batch = {
                fqn for fqn, path in unprocessed_classes.items() 
                if path.startswith(artifact_root_path + "/") or path == artifact_root_path
            }
            for fqn in processed_in_batch:
                del unprocessed_classes[fqn]

    def _correct_fqns_in_subtree(self, container_fileName: str, root_path: str):
        """Helper to set correct FQNs for all directories under a new Artifact root."""
        query = """
        MATCH (cont:Directory {fileName: $container_fileName})-[:CONTAINS]->(d:Directory)
        WHERE d.fileName STARTS WITH $root_path
        RETURN d.fileName as path
        """
        dirs_in_tree = self.neo4j_manager.execute_read_query(query, params={"container_fileName": container_fileName, "root_path": root_path})

        update_params = []
        for record in dirs_in_tree:
            dir_path = record['path']
            if len(dir_path) > len(root_path):
                relative_path = dir_path[len(root_path) + 1:]
                correct_fqn = relative_path.replace('/', '.')
                update_params.append({"path": dir_path, "fqn": correct_fqn})

        if update_params:
            update_query = """
            UNWIND $params AS p
            MATCH (cont:Directory {fileName: $container_fileName})-[:CONTAINS]->(d:Directory {fileName: p.path})
            SET d.fqn = p.fqn
            """
            self.neo4j_manager.execute_write_query(update_query, params={"container_fileName": container_fileName, "params": update_params})

    def rewrite_containment_relationships(self):
        """
        Corrects the graph's core containment structure by creating new transitive
        [:CONTAINS] relationships from the newly promoted :Artifact nodes and
        deleting the old, incorrect ones from the demoted roots.
        """
        logger.info("--- Starting Pass: Rewrite Containment Relationships ---")

        # Step 1: Add new, correct transitive relationships
        logger.info("Creating new transitive [:CONTAINS] relationships from new artifacts.")
        add_query = """
        MATCH (newArtifact:Artifact)
        MATCH (newArtifact)-[:CONTAINS*]->(descendant)
        MERGE (newArtifact)-[:CONTAINS]->(descendant)
        """
        self.neo4j_manager.execute_write_query(add_query)

        # Step 2: Delete old, incorrect transitive relationships
        logger.info("Deleting old transitive [:CONTAINS] relationships from demoted roots.")
        
        # Find the original root directories that were demoted
        demoted_roots = self.neo4j_manager.execute_read_query(
            "MATCH (d:Directory) WHERE d.fileName = d.absolute_path AND NOT d:Artifact RETURN d.fileName as fileName"
        )
        demoted_root_files = [record['fileName'] for record in demoted_roots]

        for file_name in demoted_root_files:
            delete_query = """
            MATCH (demotedRoot {fileName: $fileName})-[r:CONTAINS]->(descendant)
            WHERE demotedRoot.absolute_path IS NOT NULL AND descendant.absolute_path IS NOT NULL
            AND size(split(descendant.absolute_path, '/')) > size(split(demotedRoot.absolute_path, '/')) + 1
            DELETE r
            """
            self.neo4j_manager.execute_write_query(delete_query, params={"fileName": file_name})
            logger.info(f"Cleaned up transitive relationships for demoted root: {file_name}")

        logger.info("--- Finished Pass: Rewrite Containment Relationships ---")

    def establish_class_hierarchy(self):
        """
        Builds a clean [:CONTAINS_CLASS] parent-child hierarchy for all nodes
        within all :Artifact nodes.
        """
        logger.info("--- Starting Pass: Establish Class Hierarchy ---")

        query = "MATCH (a:Artifact) RETURN a.absolute_path AS path"
        artifacts = self.neo4j_manager.execute_read_query(query)
        
        for artifact in artifacts:
            self._establish_class_hierarchy_in_single_artifact(artifact['path'])
         
        logger.info("Established [:CONTAINS_CLASS] relationships.")
        logger.info("--- Finished Pass: Establish Class Hierarchy ---")

    def _establish_class_hierarchy_in_single_artifact(self, artifact_path: str):
        """Builds the [:CONTAINS_CLASS] hierarchy within a single artifact."""
        from collections import defaultdict
        logger.info(f"Building class hierarchy for artifact: {artifact_path}")

        # Get all directories in the artifact
        query = """
        MATCH (a:Artifact {absolute_path: $artifact_path})-[:CONTAINS]->(d:Directory)
        WHERE d.fileName IS NOT NULL
        RETURN DISTINCT d.fileName AS path, size(split(d.fileName, '/')) AS depth
        """
        nodes_with_depth = self.neo4j_manager.execute_read_query(query, params={"artifact_path": artifact_path})

        # Link class files to their parent directories
        self.neo4j_manager.execute_write_query(
            """
            UNWIND $paths AS dir_path
            MATCH (parentDir:Directory {fileName: dir_path})
            MATCH (a:Artifact {absolute_path: $artifact_path})-[:CONTAINS]->(parentDir)
            MATCH (a)-[:CONTAINS]->(t:Type:File)
            WHERE t.fileName STARTS WITH parentDir.fileName + '/'
            AND size(split(t.fileName, '/')) = size(split(parentDir.fileName, '/')) + 1
            MERGE (parentDir)-[:CONTAINS_CLASS]->(t)
            """,
            params={"paths": [item['path'] for item in nodes_with_depth], "artifact_path": artifact_path}
        )

        # Link directories to their parent directories by depth
        nodes_by_depth = defaultdict(list)
        for item in nodes_with_depth:
            nodes_by_depth[item['depth']].append(item['path'])

        for depth in sorted(nodes_by_depth.keys(), reverse=True):
            current_depth_paths = nodes_by_depth[depth]
            self.neo4j_manager.execute_write_query(
                """
                UNWIND $paths AS parent_path
                MATCH (parentDir:Directory {fileName: parent_path})
                MATCH (a:Artifact {absolute_path: $artifact_path})-[:CONTAINS]->(parentDir)
                MATCH (childDir:Directory)
                WHERE childDir.fileName STARTS WITH parentDir.fileName + '/'
                  AND size(split(childDir.fileName, '/')) = size(split(parentDir.fileName, '/')) + 1
                  AND (parentDir)-[:CONTAINS]->(childDir)
                MERGE (parentDir)-[:CONTAINS_CLASS]->(childDir)
                """,
                params={"paths": current_depth_paths, "artifact_path": artifact_path}
            )

        # Link the Artifact node to its direct children
        self.neo4j_manager.execute_write_query(
            """
            MATCH (a:Artifact {absolute_path: $artifact_path})-[:CONTAINS]->(n:Directory)
            WHERE NOT EXISTS { ()-[:CONTAINS_CLASS]->(n) }
            AND EXISTS { (n)-[:CONTAINS_CLASS*0..]->(:Type) }
            MERGE (a)-[:CONTAINS_CLASS]->(n)
            """,
            params={"artifact_path": artifact_path}
        )

    def cleanup_package_semantics(self):
        """
        Removes the 'fqn' and :Package label from any directory that is not a
        valid package.
        """
        logger.info("--- Starting Pass: Cleanup Package Semantics ---")
        query = """
        MATCH (d:Directory:Package)
        WHERE NOT ()-[:CONTAINS_CLASS]->(d)
        REMOVE d.fqn, d:Package
        """
        self.neo4j_manager.execute_write_query(query)
        logger.info("Removed 'fqn' and :Package label from non-package directories.")
        logger.info("--- Finished Pass: Cleanup Package Semantics ---")

    def link_project_to_artifacts(self):
        """
        Creates a [:CONTAINS_CLASS] relationship from the :Project node to the
        root of each identified class :Artifact.
        """
        logger.info("--- Starting Pass: Link Project to Artifacts ---")
        query = """
        MATCH (p:Project)
        MATCH (a:Artifact)
        MERGE (p)-[:CONTAINS_CLASS]->(a)
        """
        self.neo4j_manager.execute_write_query(query)
        logger.info("Linked :Project node to all :Artifact roots.")
        logger.info("--- Finished Pass: Link Project to Artifacts ---")
