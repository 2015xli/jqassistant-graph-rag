import logging
from typing import List, Dict, Any
from tqdm import tqdm
from pathlib import Path

from neo4j_manager import Neo4jManager
from java_source_parser import JavaSourceParser
from kotlin_source_parser import KotlinSourceParser


logger = logging.getLogger(__name__)


class SourceFileLinker:
    """
    Parses a project's source files and enriches the jQAssistant graph by
    connecting :Type nodes to their corresponding :SourceFile nodes via a
    [:WITH_SOURCE] relationship.
    """

    def __init__(self, neo4j_manager: Neo4jManager, project_path: Path):
        self.neo4j_manager = neo4j_manager
        self.project_path = project_path
        logger.info("Initialized SourceFileLinker.")

    def run(self):
        """
        Executes the full source file linking process: parsing the source
        directory and then updating the graph with the discovered relationships.
        """
        logger.info("\n--- Starting Pass 001: Source File Linking ---")
        try:
            source_metadata = self._parse_source_files()
            if not source_metadata:
                logger.warning(
                    "No Java or Kotlin source files found or parsed. "
                    "Skipping source file linking."
                )
                return

            relationships_created = self._enrich_graph(source_metadata)
            logger.info(
                f"Successfully created {relationships_created} new [:WITH_SOURCE] "
                "relationships from Type to File."
            )
            logger.info("--- Finished Pass 001 ---")
        except Exception as e:
            logger.error(f"Pass 001 failed: {e}", exc_info=True)
            raise

    def _parse_source_files(self) -> List[Dict[str, Any]]:
        """
        Parses all Java and Kotlin files in the project path.
        """
        all_source_metadata: List[Dict[str, Any]] = []

        java_parser = JavaSourceParser(str(self.project_path))
        all_source_metadata.extend(java_parser.parse_project())

        try:
            kotlin_parser = KotlinSourceParser(str(self.project_path))
            all_source_metadata.extend(kotlin_parser.parse_project())
        except ImportError as e:
            logger.warning(f"Kotlin parsing skipped: {e}")
        except Exception as e:
            logger.error(f"Error during Kotlin parsing: {e}")

        return all_source_metadata

    def _enrich_graph(self, source_metadata: List[Dict[str, Any]]):
        """
        Connects :File nodes to :Type nodes based on parsed metadata.
        """
        logger.info(
            f"Starting graph enrichment for {len(source_metadata)} source files."
        )

        cypher_query = """
        UNWIND $metadata AS file_data
        MATCH (file:File {fileName: file_data.path})
        UNWIND file_data.fqns AS type_fqn
        MATCH (type:Type {fqn: type_fqn})
        WHERE type:Class OR type:Interface OR type:Enum
        MERGE (type)-[r:WITH_SOURCE]->(file)
        RETURN count(r) AS relationships_created
        """
        total_relationships_created = 0
        batch_size = 1000

        for i in tqdm(
            range(0, len(source_metadata), batch_size),
            desc="Enriching Neo4j graph",
        ):
            batch = source_metadata[i : i + batch_size]
            try:
                summary = self.neo4j_manager.execute_write_query(
                    cypher_query, params={"metadata": batch}
                )
                total_relationships_created += summary.relationships_created
            except Exception as e:
                logger.error(
                    f"Error enriching graph with batch starting at index {i}: {e}"
                )

        return total_relationships_created
