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
        self.relocated_artifacts_map = {}
        logger.info("Initialized ArtifactDataNormalizer.")

    def merge_duplicate_types(self):
        """
        Finds and merges duplicate :Type nodes created by jQAssistant scans.
        It merges the "phantom" type node created by a [:REQUIRES] relationship
        into the "real" type node created by a [:CONTAINS] relationship.
        """
        logger.info("--- Starting Pass: Merge Duplicate Types ---")
        query = """
        MATCH (a:Artifact:Directory)
        MATCH (a)-[:CONTAINS]->(realType:Type)
        WHERE realType.fqn IS NOT NULL AND realType.fileName IS NOT NULL
        MATCH (a)-[:REQUIRES]->(phantomType:Type)
        WHERE phantomType.fqn IS NOT NULL AND phantomType.fileName IS NOT NULL
        // This condition ensures we correctly identify the real and phantom nodes
        AND realType.fqn = phantomType.fqn AND realType.fileName ENDS WITH phantomType.fileName AND realType.fileName <> phantomType.fileName
        WITH phantomType, realType
        CALL apoc.refactor.mergeNodes([realType, phantomType], {
            properties: 'discard', 
            mergeRels: true
        }) YIELD node
        RETURN count(node) AS merged_nodes
        """
        result = self.neo4j_manager.execute_write_query(query)
        #merged = result.nodes_deleted
        # The result from apoc.refactor.mergeNodes is a stream, not a summary.
        # We can't easily get the count here without more complex result handling.
        # A simple log message will suffice.
        logger.info(f"Completed merging of duplicate :Type nodes.")
        logger.info("--- Finished Pass: Merge Duplicate Types ---")

        logger.info("--- Starting Pass: Merge Duplicate Members ---")
        query = """
        MATCH (a:Artifact:Directory) -[:CONTAINS]->(t:Type)
        MATCH (t)-[:DECLARES]->(realMember:Member)
        MATCH (t)-[:DECLARES]->(phantomMember:Member)
        //We need make sure we know which member is real (has name) and which is phantom (no name)
        //Both have signature.
        WHERE realMember.name IS NOT NULL AND phantomMember.signature IS NOT NULL 
            AND realMember.signature = phantomMember.signature
            AND elementId(realMember) <> elementId(phantomMember)
        WITH phantomMember, realMember
        CALL apoc.refactor.mergeNodes([realMember, phantomMember], {
            properties: 'discard', 
            mergeRels: true
        }) YIELD node
        RETURN count(node) AS merged_nodes
        """
        result = self.neo4j_manager.execute_write_query(query)
        logger.info(f"Completed merging of duplicate :Member nodes.")
        logger.info("--- Finished Pass: Merge Duplicate Members ---")

    def relocate_directory_artifacts(self):
        """
        Validates scanned :Directory:Artifacts. If incorrect, demotes the
        original and promotes the true roots of class hierarchies to be :Artifacts.
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
        """
        Validates a single scanned artifact. If it's not a true classpath root,
        it demotes it and promotes the correct sub-directories.
        """
        logger.info(f"Validating potential artifact container: {artifact_fileName}")
        self.relocated_artifacts_map[artifact_fileName] = []
        
        query = """
        MATCH (a:Artifact:Directory {fileName: $artifact_fileName})-[:CONTAINS]->(c:File:Class)
        WHERE c.fqn IS NOT NULL AND c.fileName IS NOT NULL
        RETURN c.fqn AS fqn, c.fileName AS path
        """
        class_files = self.neo4j_manager.execute_read_query(query, params={"artifact_fileName": artifact_fileName})

        if not class_files:
            logger.info(f"No class files found in {artifact_fileName}. Assuming it's not a class artifact.")
            self.neo4j_manager.execute_write_query(
                "MATCH (a:Directory {fileName: $fileName}) WHERE a:Artifact REMOVE a:Artifact",
                params={"fileName": artifact_fileName}
            )
            return

        unprocessed_classes = {c['fqn']: c['path'] for c in class_files}
        true_artifact_roots = set()
        
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
            true_artifact_roots.add(artifact_root_path)

            processed_in_batch = {
                fqn for fqn, path in unprocessed_classes.items() 
                if path.startswith(artifact_root_path + "/") or path == artifact_root_path
            }
            for fqn in processed_in_batch:
                del unprocessed_classes[fqn]

        original_artifact_relative_path = ""
        if original_artifact_relative_path in true_artifact_roots and len(true_artifact_roots) == 1:
            logger.info(f"Artifact '{artifact_fileName}' is correctly labeled. No changes needed.")
            self.relocated_artifacts_map[artifact_fileName] = [artifact_fileName]
            self._correct_fqns_in_subtree(artifact_fileName, original_artifact_relative_path)
            return

        logger.info(f"Relocating artifact label from '{artifact_fileName}'.")
        self.neo4j_manager.execute_write_query(
            "MATCH (a:Directory {fileName: $fileName}) WHERE a:Artifact REMOVE a:Artifact",
            params={"fileName": artifact_fileName}
        )

        for root_path in true_artifact_roots:
            # Pre-calculate the absolute path of the node to be promoted.
            new_artifact_absolute_path = artifact_fileName + root_path
            
            self.neo4j_manager.execute_write_query(
                """
                MATCH (cont:Directory {fileName: $artifact_fileName})-[:CONTAINS]->(d:Directory {fileName: $root_path})
                SET d:Artifact, d.fileName = d.absolute_path
                """,
                params={"artifact_fileName": artifact_fileName, "root_path": root_path}
            )
            logger.info(f"Promoted '{root_path}' to be a new :Artifact and updated its fileName.")
            self.relocated_artifacts_map[artifact_fileName].append(new_artifact_absolute_path)
            self._correct_fqns_in_subtree(artifact_fileName, root_path)

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
        
        demoted_roots = list(self.relocated_artifacts_map.keys())
        if not demoted_roots:
            logger.info("No artifacts were demoted. Skipping transitive relationship cleanup.")
            logger.info("--- Finished Pass: Rewrite Containment Relationships ---")
            return

        for file_name in demoted_roots:
            # Only run cleanup if new artifacts were actually promoted inside
            if self.relocated_artifacts_map.get(file_name):
                delete_query = """
                MATCH (demotedRoot {fileName: $fileName})-[r:CONTAINS]->(descendant)
                WHERE demotedRoot.absolute_path IS NOT NULL AND descendant.absolute_path IS NOT NULL
                AND size(split(descendant.absolute_path, '/')) > size(split(demotedRoot.absolute_path, '/')) + 1
                DELETE r
                """
                self.neo4j_manager.execute_write_query(delete_query, params={"fileName": file_name})
                logger.info(f"Cleaned up transitive relationships for demoted root: {file_name}")

        logger.info("--- Finished Pass: Rewrite Containment Relationships ---")

    def rewrite_requirement_relationships(self):
        """
        Relocates [:REQUIRES] relationships from the demoted artifact roots to the
        newly promoted, correct :Artifact nodes.
        """
        logger.info("--- Starting Pass: Rewrite Requirement Relationships ---")

        for demoted_root, promoted_artifacts in self.relocated_artifacts_map.items():
            if not promoted_artifacts:
                continue
            
            # This query is now much simpler as it operates on pre-filtered data
            self.neo4j_manager.execute_write_query(
                """
                MATCH (demotedRoot {fileName: $demoted_root_fileName})
                UNWIND $promoted_artifact_fileNames AS new_artifact_fileName
                MATCH (newArtifact:Artifact:Directory {fileName: new_artifact_fileName})
                
                MATCH (newArtifact)-[:CONTAINS]->(internalType:Type)
                MATCH (internalType)-[:DEPENDS_ON]->(requiredType:Type)
                WHERE (demotedRoot)-[:REQUIRES]->(requiredType)
                
                MERGE (newArtifact)-[:REQUIRES]->(requiredType)
                """,
                params={
                    "demoted_root_fileName": demoted_root,
                    "promoted_artifact_fileNames": promoted_artifacts
                }
            )
            logger.info(f"Relocated [:REQUIRES] relationships for new artifacts under {demoted_root}")

        if self.relocated_artifacts_map:
            self.neo4j_manager.execute_write_query(
                """
                UNWIND $demoted_root_files AS fileName
                MATCH (demotedRoot {fileName: fileName})-[r:REQUIRES]->(t:Type)
                DELETE r
                """,
                params={"demoted_root_files": list(self.relocated_artifacts_map.keys())}
            )
            logger.info("Deleted old [:REQUIRES] relationships from all demoted roots.")

        logger.info("--- Finished Pass: Rewrite Requirement Relationships ---")

    def establish_class_hierarchy(self):
        """
        Builds a clean [:CONTAINS_CLASS] parent-child hierarchy for all nodes
        within all :Artifact nodes.
        """
        logger.info("--- Starting Pass: Establish Class Hierarchy ---")

        # Get all unique artifact paths from the relocation map and original JARs
        all_artifact_paths = set()
        for promoted_list in self.relocated_artifacts_map.values():
            for path in promoted_list:
                all_artifact_paths.add(path)
        
        jar_artifacts = self.neo4j_manager.execute_read_query(
            "MATCH (a:Jar:Artifact) RETURN a.fileName AS path"
        )
        for record in jar_artifacts:
            all_artifact_paths.add(record['path'])

        for path in all_artifact_paths:
            self._establish_class_hierarchy_in_single_artifact(path)
         
        logger.info("Established [:CONTAINS_CLASS] relationships.")
        logger.info("--- Finished Pass: Establish Class Hierarchy ---")

    def _establish_class_hierarchy_in_single_artifact(self, artifact_path: str):
        """Builds the [:CONTAINS_CLASS] hierarchy within a single artifact."""
        from collections import defaultdict
        logger.info(f"Building class hierarchy for artifact: {artifact_path}")

        # Get all directories in the artifact
        query = """
        MATCH (a:Artifact {fileName: $artifact_path})-[:CONTAINS]->(d:Directory)
        WHERE d.fileName IS NOT NULL
        RETURN DISTINCT d.fileName AS path, size(split(d.fileName, '/')) AS depth
        """
        nodes_with_depth = self.neo4j_manager.execute_read_query(query, params={"artifact_path": artifact_path})

        # Link class files to their parent directories
        self.neo4j_manager.execute_write_query(
            """
            UNWIND $paths AS dir_path
            MATCH (parentDir:Directory {fileName: dir_path})
            MATCH (a:Artifact {fileName: $artifact_path})-[:CONTAINS]->(parentDir)
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
                MATCH (a:Artifact {fileName: $artifact_path})-[:CONTAINS]->(parentDir)
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
            MATCH (a:Artifact {fileName: $artifact_path})-[:CONTAINS]->(n:Directory)
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
        MATCH (a:Artifact) WHERE NOT a:Maven
        MERGE (p)-[:CONTAINS_CLASS]->(a)
        """
        self.neo4j_manager.execute_write_query(query)
        logger.info("Linked :Project node to all :Artifact roots.")
        logger.info("--- Finished Pass: Link Project to Artifacts ---")
