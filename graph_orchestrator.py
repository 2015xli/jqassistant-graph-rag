import logging
import os
from neo4j_manager import Neo4jManager
from graph_normalizer import GraphNormalizer
from source_file_linker import SourceFileLinker
from pathlib import Path

logger = logging.getLogger(__name__)


class GraphOrchestrator:
    """
    Manages and executes the sequence of enrichment passes.
    It determines the project's root path and then runs the necessary
    enrichment components in the correct order.
    """

    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        self.project_path = self._determine_project_root()
        self.project_name = self.project_path.name
        logger.info(
            f"Initialized GraphOrchestrator for project: {self.project_name}"
        )

    def _determine_project_root(self) -> Path:
        """
        Auto-detects the project's root path from the graph by finding the
        common path of all directory-based :Artifact nodes.
        """
        logger.info("Auto-detecting project path from graph artifacts...")
        query = """
        MATCH (a:Artifact:Directory)
        WHERE a.fileName IS NOT NULL
        RETURN a.fileName AS path
        """
        results = self.neo4j_manager.execute_read_query(query)

        artifact_paths = [
            res["path"] for res in results if res and res.get("path")
        ]
        if not artifact_paths:
            raise ValueError(
                "Could not auto-detect project path. No directory-based :Artifact "
                "nodes with 'fileName' property found in the graph."
            )

        project_path_str = os.path.commonpath(artifact_paths)
        logger.info(f"Auto-detected project path: {project_path_str}")

        project_path = Path(project_path_str).resolve()
        if not project_path.is_dir():
            raise ValueError(
                f"Auto-detected project path '{project_path}' is not a valid directory."
            )
        return project_path

    def run_enrichment_passes(self):
        """
        Executes the full sequence of graph enrichment passes by instantiating
        and running the necessary components in order.
        """
        logger.info(
            f"--- Starting All Enrichment Passes for project: {self.project_name} ---"
        )

        # Step 1: Link source files to the graph
        source_linker = SourceFileLinker(self.neo4j_manager, self.project_path)
        source_linker.run()

        # Step 2: Run all graph normalization passes
        graph_normalizer = GraphNormalizer(self.neo4j_manager, self.project_path)
        graph_normalizer.run_all_passes()

        logger.info(
            f"--- All Enrichment Passes for project: {self.project_name} Complete ---"
        )


    
