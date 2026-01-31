import logging
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class PackageDataNormalizer:
    """
    Handles the normalization of package-related data in the graph.
    This includes validating package structures from class files, correcting
    'fqn' properties, and establishing a clean, unified ':ClassTree' hierarchy.
    """

    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized PackageDataNormalizer.")

    def label_jar_artifacts_as_class_trees(self):
        """
        Finds all JAR artifacts and labels them as :ClassTree, as they are
        considered to have a valid, reliable package structure.
        """
        logger.info("--- Starting Pass: Label JAR Artifacts as Class Trees ---")
        query = """
        MATCH (j:Jar:Artifact)
        SET j:ClassTree
        RETURN count(j) AS jar_artifacts_labeled
        """
        result = self.neo4j_manager.execute_write_query(query)
        labels_added = result.labels_added
        logger.info(f"Labeled {labels_added} JAR artifacts as :ClassTree.")
        logger.info("--- Finished Pass: Label JAR Artifacts as Class Trees ---")

    def normalize_directory_packages(self):
        """
        Validates directory structures against class FQNs to find and label
        legitimate package trees within :Directory:Artifact nodes.
        """
        logger.info("--- Starting Pass: Normalize Directory Packages ---")
        
        artifacts = self.neo4j_manager.execute_read_query(
            "MATCH (a:Directory:Artifact) RETURN a.fileName AS fileName"
        )
        artifact_files = [record['fileName'] for record in artifacts]

        for artifact_fileName in artifact_files:
            self._process_single_directory_artifact(artifact_fileName)
        
        logger.info("--- Finished Pass: Normalize Directory Packages ---")

    def _process_single_directory_artifact(self, artifact_fileName: str):
        """Helper to process one directory artifact at a time."""
        logger.info(f"Processing directory artifact: {artifact_fileName}")
        
        query = """
        MATCH (a:Artifact:Directory {fileName: $artifact_fileName})-[:CONTAINS]->(c:File:Class)
        WHERE c.fqn IS NOT NULL AND c.fileName IS NOT NULL
        RETURN c.fqn AS fqn, c.fileName AS path
        """
        class_files = self.neo4j_manager.execute_read_query(query, params={"artifact_fileName": artifact_fileName})

        if not class_files:
            logger.info(f"No class files found in artifact {artifact_fileName}. Skipping.")
            return

        unprocessed_classes = {c['fqn']: c['path'] for c in class_files}
        
        while unprocessed_classes:
            anchor_fqn = max(unprocessed_classes.keys(), key=len)
            anchor_path = unprocessed_classes[anchor_fqn]

            package_parts = anchor_fqn.split('.')[:-1]
            package_as_path = "/" + "/".join(package_parts) if package_parts else ""

            anchor_dir = "/".join(anchor_path.split('/')[:-1])

            if not anchor_dir.endswith(package_as_path):
                logger.warning(f"Mismatch for {anchor_fqn}: dir '{anchor_dir}' does not match package path '{package_as_path}'.")
                del unprocessed_classes[anchor_fqn]
                continue

            class_tree_root_path = anchor_dir[:-len(package_as_path)] if package_as_path else anchor_dir
            
            self.neo4j_manager.execute_write_query(
                """
                MATCH (a:Directory:Artifact {fileName: $artifact_fileName})-[:CONTAINS]->(d:Directory {fileName: $root_path})
                SET d:ClassTree
                """,
                params={"artifact_fileName": artifact_fileName, "root_path": class_tree_root_path}
            )
            logger.info(f"Labeled '{class_tree_root_path}' as a :ClassTree root.")

            self._correct_fqns_in_subtree(artifact_fileName, class_tree_root_path)

            processed_in_batch = {
                fqn for fqn, path in unprocessed_classes.items() 
                if path.startswith(class_tree_root_path + "/") or path == class_tree_root_path
            }
            for fqn in processed_in_batch:
                del unprocessed_classes[fqn]

    def _correct_fqns_in_subtree(self, artifact_fileName: str, root_path: str):
        """Helper to set correct FQNs for all directories under a ClassTree root."""
        query = """
        MATCH (a:Directory:Artifact {fileName: $artifact_fileName})-[:CONTAINS]->(d:Directory)
        WHERE d.fileName STARTS WITH $root_path
        RETURN d.fileName as path
        """
        dirs_in_tree = self.neo4j_manager.execute_read_query(query, params={"artifact_fileName": artifact_fileName, "root_path": root_path})

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
            MATCH (a:Directory:Artifact {fileName: $artifact_fileName})-[:CONTAINS]->(d:Directory {fileName: p.path})
            SET d.fqn = p.fqn
            """
            self.neo4j_manager.execute_write_query(update_query, params={"artifact_fileName": artifact_fileName, "params": update_params})
            logger.info(f"Corrected FQNs for {len(update_params)} directories under '{root_path}'.")

    def establish_class_hierarchy(self):
        """
        Builds a clean [:CONTAINS_CLASS] parent-child hierarchy for all nodes
        within all :ClassTree nodes.
        """
        logger.info("--- Starting Pass: Establish Class Hierarchy ---")

        query = """
        MATCH (ct:ClassTree)
        RETURN ct.absolute_path AS path
        """
        classtrees = self.neo4j_manager.execute_read_query(query)
        
        for classtree in classtrees:
            self._establish_class_hierarchy_in_single_classtree(classtree['path'])
         
        logger.info("Established [:CONTAINS_CLASS] relationships.")
        logger.info("--- Finished Pass: Establish Class Hierarchy ---")

    def _establish_class_hierarchy_in_single_classtree(self, classtree_path: str):
        """
        Builds a clean [:CONTAINS_CLASS] parent-child hierarchy within a single :ClassTree.
        """
        logger.info(f"--- Starting Pass: Establish Class Hierarchy in {classtree_path}---")
        from collections import defaultdict

        # check if there are any class files in the classtree
        query = """
        MATCH (ct:ClassTree {absolute_path: $classtree_path})-[:CONTAINS*]->(f:File)
        WHERE f.fileName IS NOT NULL
        RETURN DISTINCT f.fileName AS path, size(split(f.fileName, '/')) AS depth
        """
        files_with_depth = self.neo4j_manager.execute_read_query(
            query,
            params={"classtree_path": classtree_path}
        )

        if not files_with_depth:
            logger.warning("No class files found within ClassTrees to build hierarchy.")
            return

        # Get all the directories in the classtree
        query = """
        MATCH (ct:ClassTree {absolute_path: $classtree_path})-[:CONTAINS*]->(n:Directory)
        WHERE n.fileName IS NOT NULL
        RETURN DISTINCT n.fileName AS path, size(split(n.fileName, '/')) AS depth
        """
        nodes_with_depth = self.neo4j_manager.execute_read_query(
            query,
            params={"classtree_path": classtree_path}
        )

        # Link the class files to their parent directories
        self.neo4j_manager.execute_write_query(
            """
            UNWIND $paths AS dir_path
            MATCH (parentDir:Directory {fileName: dir_path})
            MATCH (t:Type:File)
            WHERE t.fileName STARTS WITH parentDir.fileName + '/'
            AND size(split(t.fileName, '/')) = size(split(parentDir.fileName, '/')) + 1
            AND (parentDir)-[:CONTAINS]->(t)
            MERGE (parentDir)-[:CONTAINS_CLASS]->(t)
            """,
            params={"paths": [item['path'] for item in nodes_with_depth]}
        )

        # Link the directories to their parent directories by depth
        nodes_by_depth = defaultdict(list)
        for item in nodes_with_depth:
            nodes_by_depth[item['depth']].append(item['path'])

        for depth in sorted(nodes_by_depth.keys(), reverse=True):
            current_depth_paths = nodes_by_depth[depth]
            
            self.neo4j_manager.execute_write_query(
                """
                UNWIND $paths AS parent_path
                MATCH (parentDir:Directory {fileName: parent_path})
                MATCH (childDir:Directory)
                WHERE childDir.fileName STARTS WITH parentDir.fileName + '/'
                  AND size(split(childDir.fileName, '/')) = size(split(parentDir.fileName, '/')) + 1
                  AND EXISTS { (childDir)-[:CONTAINS_CLASS]->() }
                  AND (parentDir)-[:CONTAINS]->(childDir)
                MERGE (parentDir)-[:CONTAINS_CLASS]->(childDir)
                """,
                params={"paths": current_depth_paths}
            )

        # Link the ClassTree node to its direct children
        self.neo4j_manager.execute_write_query(
            """
            MATCH (ct:ClassTree {absolute_path: $classtree_path})-[:CONTAINS]->(n:Directory)
            WHERE EXISTS { (n)-[:CONTAINS_CLASS]->() } 
            AND NOT EXISTS { ()-[:CONTAINS_CLASS]->(n) }
            MERGE (ct)-[:CONTAINS_CLASS]->(n)
            """,
            params={"classtree_path": classtree_path}
        )


    def cleanup_package_semantics(self):
        """
        Removes the 'fqn' property from any directory that is not a valid
        package, including the ClassTree roots themselves.
        """
        logger.info("--- Starting Pass: Cleanup FQN Properties ---")
        query = """
        MATCH (d:Directory:Package)
        WHERE NOT ()-[:CONTAINS_CLASS]->(d)
        REMOVE d.fqn, d:Package
        """
        self.neo4j_manager.execute_write_query(query)
        logger.info("Removed 'fqn' and :Package label from non-package directories and ClassTree roots.")
        logger.info("--- Finished Pass: Cleanup FQN Properties ---")

    def link_project_to_class_trees(self):
        """
        Creates a [:CONTAINS_CLASS] relationship from the :Project node to the
        root of each identified :ClassTree.
        """
        logger.info("--- Starting Pass: Link Project to Class Trees ---")
        query = """
        MATCH (p:Project)
        MATCH (ct:ClassTree)
        MERGE (p)-[:CONTAINS_CLASS]->(ct)
        """
        self.neo4j_manager.execute_write_query(query)
        logger.info("Linked :Project node to all :ClassTree roots.")
        logger.info("--- Finished Pass: Link Project to Class Trees ---")
