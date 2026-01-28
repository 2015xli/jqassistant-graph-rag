import logging
import os
from pathlib import Path
from collections import defaultdict
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class GraphTreeBuilder:
    """
    Handles the third phase of graph normalization: establishing a clean,
    hierarchical tree structure for the project.
    """

    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        self.project_path = None
        self.project_name = None
        logger.info("Initialized GraphTreeBuilder.")

    def create_project_node(self):
        """
        Auto-detects the project's root path, creates a single :Project node,
        and links all :Artifact nodes to it.
        """
        logger.info("--- Starting Pass: Create Project Node ---")
        
        # 1. Auto-detect project root from the graph
        query = """
        MATCH (a:Artifact:Directory)
        WHERE a.fileName IS NOT NULL
        RETURN a.fileName AS path
        """
        results = self.neo4j_manager.execute_read_query(query)
        artifact_paths = [res["path"] for res in results if res and res.get("path")]
        if not artifact_paths:
            raise ValueError(
                "Could not auto-detect project path. No directory-based :Artifact "
                "nodes with 'fileName' property found in the graph."
            )
        
        project_path_str = os.path.commonpath(artifact_paths)
        self.project_path = Path(project_path_str).resolve()
        self.project_name = self.project_path.name
        logger.info(f"Auto-detected project path: {self.project_path}")

        # 2. Create :Project node and link artifacts
        self.neo4j_manager.execute_write_query(
            """
        MERGE (p:Project {name: $projectName})
        ON CREATE SET p.creationTimestamp = datetime()
        SET p.absolute_path = $projectPath
        WITH p
        MATCH (a:Artifact) WHERE a:Directory|Jar|War|Ear
        MERGE (p)-[:CONTAINS]->(a)
        """,
            params={
                "projectName": self.project_name,
                "projectPath": str(self.project_path),
            },
        )
        logger.info(f"Created :Project node for '{self.project_name}' and linked artifacts.")
        logger.info("--- Finished Pass: Create Project Node ---")
        return self.project_path

    def establish_source_hierarchy(self):
        """
        Establishes a direct hierarchical structure for source entities
        using [:CONTAINS_SOURCE], processing level by level.
        """
        if not self.project_path:
            raise ValueError("Project path has not been determined. Run create_project_node() first.")
            
        logger.info("--- Starting Pass: Establish Direct Source Hierarchy ---")

        # 1. Get all directories with their depths
        query_all_dirs = """
        MATCH (d:Directory)
        WHERE d.absolute_path IS NOT NULL
        RETURN d.absolute_path AS path, size(split(d.absolute_path, '/')) AS depth
        """
        all_dirs_with_depth = self.neo4j_manager.execute_read_query(query_all_dirs)

        if not all_dirs_with_depth:
            logger.warning("No directories with absolute_path found to establish hierarchy.")
            return

        # Link directories to their direct SourceFile children
        self.neo4j_manager.execute_write_query(
            """
            UNWIND $paths AS dir_path
            MATCH (parentDir:Directory {absolute_path: dir_path})
            MATCH (sf:SourceFile)
            WHERE sf.absolute_path STARTS WITH parentDir.absolute_path + '/'
                AND size(split(sf.absolute_path, '/')) = size(split(parentDir.absolute_path, '/')) + 1
            MERGE (parentDir)-[:CONTAINS_SOURCE]->(sf)
            """,
            params={"paths": [d['path'] for d in all_dirs_with_depth]}
        )


        dirs_by_depth = defaultdict(list)
        for item in all_dirs_with_depth:
            dirs_by_depth[item['depth']].append(item['path'])

        # 2. Process levels from deepest to shallowest
        for depth in sorted(dirs_by_depth.keys(), reverse=True):
            current_depth_dir_paths = dirs_by_depth[depth]
            
            # Link directories to their direct Directory children
            self.neo4j_manager.execute_write_query(
                """
                UNWIND $paths AS parent_path
                MATCH (parentDir:Directory {absolute_path: parent_path})
                MATCH (childDir:Directory)
                WHERE childDir.absolute_path STARTS WITH parentDir.absolute_path + '/'
                  AND size(split(childDir.absolute_path, '/')) = size(split(parentDir.absolute_path, '/')) + 1
                  AND EXISTS {(childDir)-[:CONTAINS_SOURCE]->()}
                MERGE (parentDir)-[:CONTAINS_SOURCE]->(childDir)
                """,
                params={"paths": current_depth_dir_paths}
            )

        logger.info("Established [:CONTAINS_SOURCE] relationships between directories and source files.")

        # 3. Link Project node to top-level artifact directories
        self.neo4j_manager.execute_write_query(
            """
            MATCH (p:Project {absolute_path: $projectPath})
            MATCH (d:Directory:Artifact)
            WHERE EXISTS {(d)-[:CONTAINS_SOURCE]->()}
            MERGE (p)-[:CONTAINS_SOURCE]->(d)
            """,
            params={"projectPath": str(self.project_path)}
        )
        logger.info("Linked :Project node to top-level source directories.")
        logger.info("--- Finished Pass: Establish Direct Source Hierarchy ---")
