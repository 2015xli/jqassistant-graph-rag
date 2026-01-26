import logging
import os
from neo4j_manager import Neo4jManager
from pathlib import Path

logger = logging.getLogger(__name__)


class GraphNormalizer:
    """
    Handles all graph normalization passes, including path correction,
    hierarchy establishment, and stable ID generation.
    """

    def __init__(self, neo4j_manager: Neo4jManager, project_path: Path):
        self.neo4j_manager = neo4j_manager
        self.project_path = project_path
        self.project_name = project_path.name
        logger.info("Initialized GraphNormalizer.")

    def run_all_passes(self):
        """
        Executes the full sequence of graph normalization passes.
        """
        self._create_project_node()
        self._identify_and_label_entry_nodes()
        self._add_absolute_path_to_filesystem_nodes()
        self._label_source_files()
        self._identify_entities() # Entity ID generation must happen before hierarchical linking for dependency_ids
        self._establish_direct_source_hierarchy()
        self._link_members_to_source_files()
        

    def _create_project_node(self):
        """Creates a single :Project node."""
        self.neo4j_manager.execute_write_query(
            """
        MERGE (p:Project {name: $projectName})
        ON CREATE SET p.creationTimestamp = datetime()
        SET p.absolute_path = $projectPath
        """,
            params={
                "projectName": self.project_name,
                "projectPath": str(self.project_path),
            },
        )
        logger.info("Created a single :Project node with the determined path.")

    def _identify_and_label_entry_nodes(self):
        """Identifies :Artifact nodes as :Entry points and links them to the :Project node."""
        query = """
        MATCH (a:Artifact:Directory)
        SET a:Entry
        WITH a
        MATCH (p:Project)
        MERGE (p)-[:CONTAINS_SOURCE]->(a)
        RETURN count(a) AS entryNodesCreated
        """
        result = self.neo4j_manager.execute_write_query(
            query,
            params={},
        )
        logger.info(
            f"Labeled {result.labels_added} :Artifact nodes as :Entry points and linked to :Project."
        )

    def _add_absolute_path_to_filesystem_nodes(self):
        """
        Adds 'absolute_path' property to all File and Directory nodes based on
        their relative path and the project root.
        """
        logger.info("Adding 'absolute_path' property to filesystem nodes...")
        query = """
        MATCH (e:Entry)-[:CONTAINS]->(f:File|Directory)
        SET f.absolute_path = e.fileName + f.fileName
        RETURN count(f) AS pathsNormalized
        """
        result = self.neo4j_manager.execute_write_query(
            query, params={}
        )
        logger.info(
            f"Set absolute_path for {result.properties_set} File/Directory nodes."
        )

    def _identify_entities(self):
        """
        Implements the Entity Identification pass.
        Creates a stable, unique 'entity_id' for all relevant nodes and
        labels them as :Entity.
        """
        logger.info("\n--- Starting Pass: Entity Identification ---")

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

        # Generate entity_id for nodes in a "virtual file system" container of an Artifact node
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
        logger.info("--- Finished Pass: Entity Identification ---")

    def _label_source_files(self):
        """
        Implements Pass 020: Identifies and labels :File nodes that represent
        actual Java (.java) or Kotlin (.kt) source code files as :SourceFile.
        """
        logger.info("\n--- Starting Pass 020: Label Source Files ---")
        query = """
        MATCH (f:File)
        WHERE f.absolute_path IS NOT NULL
        AND (f.absolute_path ENDS WITH '.java' OR f.absolute_path ENDS WITH '.kt')
        SET f:SourceFile
        RETURN count(f) AS sourceFilesLabeled
        """
        result = self.neo4j_manager.execute_write_query(query)
        logger.info(f"Labeled {result.labels_added} files as :SourceFile.")
        logger.info("--- Finished Pass 020 ---")

    def _establish_direct_source_hierarchy(self):
        """
        Establishes a clear, direct hierarchical structure for source entities
        using [:CONTAINS_SOURCE], processing level by level from deepest to shallowest.
        """
        logger.info("\n--- Starting Pass 030: Establish Direct Source Hierarchy ---")

        # 1. Get all directories with their depths
        query_all_dirs = """
        MATCH (d:Directory)
        WHERE d.absolute_path IS NOT NULL
        RETURN d.entity_id AS id, d.absolute_path AS path, size(split(d.absolute_path, '/')) AS depth
        """
        all_dirs_with_depth = self.neo4j_manager.execute_read_query(query_all_dirs)

        if not all_dirs_with_depth:
            logger.info("No directories found to establish hierarchy for.")
            return

        # Group directories by depth
        from collections import defaultdict
        dirs_by_depth = defaultdict(list)
        for item in all_dirs_with_depth:
            dirs_by_depth[item['depth']].append(item['id'])

        total_sf_relationships_created = 0
        total_dir_relationships_created = 0

        # Process levels from deepest to shallowest
        for depth in sorted(dirs_by_depth.keys(), reverse=True):
            current_depth_dir_ids = dirs_by_depth[depth]
            logger.info(f"Establishing hierarchy for {len(current_depth_dir_ids)} directories at depth {depth}.")

            # Query 1: Link directories to their direct SourceFile children
            query_dir_to_sf = """
            UNWIND $current_depth_ids AS dir_id
            MATCH (parentDir:Directory {entity_id: dir_id})
            MATCH (sf:SourceFile)
            WHERE sf.absolute_path STARTS WITH parentDir.absolute_path + '/'
              AND size(split(sf.absolute_path, '/')) = size(split(parentDir.absolute_path, '/')) + 1
            MERGE (parentDir)-[r:CONTAINS_SOURCE]->(sf)
            RETURN count(r) AS relationshipsCreated
            """
            result_dir_to_sf = self.neo4j_manager.execute_write_query(
                query_dir_to_sf, params={"current_depth_ids": current_depth_dir_ids}
            )
            total_sf_relationships_created += result_dir_to_sf.relationships_created

            # Query 2: Link directories to their direct Directory children
            query_dir_to_dir = """
            UNWIND $current_depth_ids AS parent_dir_id
            MATCH (parentDir:Directory {entity_id: parent_dir_id})
            MATCH (childDir:Directory)
            WHERE childDir.absolute_path STARTS WITH parentDir.absolute_path + '/'
              AND size(split(childDir.absolute_path, '/')) = size(split(parentDir.absolute_path, '/')) + 1
              AND NOT childDir:Entry // Exclude Entry nodes as children of other directories
            MERGE (parentDir)-[r:CONTAINS_SOURCE]->(childDir)
            RETURN count(r) AS relationshipsCreated
            """
            result_dir_to_dir = self.neo4j_manager.execute_write_query(
                query_dir_to_dir, params={"current_depth_ids": current_depth_dir_ids}
            )
            total_dir_relationships_created += result_dir_to_dir.relationships_created

        logger.info(
            f"Created {total_sf_relationships_created} [:CONTAINS_SOURCE] "
            "relationships from directories to source files."
        )
        logger.info(
            f"Created {total_dir_relationships_created} [:CONTAINS_SOURCE] "
            "relationships between directories."
        )
        logger.info("--- Finished Pass 030 ---")

    def _link_members_to_source_files(self):
        """
        Implements Pass 035: Creates [:WITH_SOURCE] relationships directly from
        :Method and :Field nodes to their corresponding :SourceFile nodes.
        """
        logger.info("\n--- Starting Pass 035: Link Members to Source Files ---")
        query = """
        MATCH (type:Type)-[:DECLARES]->(member:Member)
        MATCH (type)-[:WITH_SOURCE]->(sourceFile:SourceFile)
        MERGE (member)-[r:WITH_SOURCE]->(sourceFile)
        RETURN count(r) AS relationshipsCreated
        """
        result = self.neo4j_manager.execute_write_query(query)
        logger.info(
            f"Created {result.relationships_created} [:WITH_SOURCE] "
            "relationships from members to source files."
        )
        logger.info("--- Finished Pass 035 ---")
