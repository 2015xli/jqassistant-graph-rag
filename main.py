import argparse
import logging
import sys
from pathlib import Path

# Import modules from the same directory
from input_params import add_neo4j_args, add_project_path_args, add_logging_args
from java_source_parser import JavaSourceParser
from kotlin_source_parser import KotlinSourceParser # New import
from graph_enricher import GraphEnricher
from neo4j_manager import Neo4jManager
from log_manager import init_logging

logger = logging.getLogger(__name__) # Keep this for main.py's own logging

def main():
    parser = argparse.ArgumentParser(
        description="Enrich a jQAssistant Neo4j graph by connecting Java/Kotlin source files to Type:Class nodes." # Updated description
    )

    add_project_path_args(parser)
    add_neo4j_args(parser)
    add_logging_args(parser)

    args = parser.parse_args()

    # Initialize logging based on parsed arguments
    init_logging(args.log_level)
    uri, user, password = args.uri, args.user, args.password
    #uri, user, password = "bolt://localhost:7688", "neo4j", "neo4j"

    # Resolve project path
    project_path = Path(args.project_path).resolve()
    if not project_path.is_dir():
        logger.error(f"Error: Project path '{project_path}' is not a valid directory.")
        sys.exit(1)
    
    logger.info(f"Starting jQAssistant Graph RAG enrichment for project: {project_path}")

    try:
        # Step 1: Parse Java and Kotlin source files
        all_source_metadata = []

        java_parser = JavaSourceParser(str(project_path))
        java_metadata = java_parser.parse_project()
        all_source_metadata.extend(java_metadata)

        kotlin_parser = KotlinSourceParser(str(project_path))
        kotlin_metadata = kotlin_parser.parse_project()
        all_source_metadata.extend(kotlin_metadata)

        if not all_source_metadata:
            logger.warning("No Java or Kotlin source files found or parsed. Exiting.")
            sys.exit(0)

        # Step 2: Enrich Neo4j graph
        # Instantiate Neo4jManager and pass it to GraphEnricher
        with Neo4jManager(uri=uri, user=user, password=password) as neo4j_mgr:
            enricher = GraphEnricher(neo4j_manager=neo4j_mgr) # Pass manager instance
            relationships_created = enricher.enrich_graph(all_source_metadata)
            logger.info(f"Successfully created {relationships_created} new [:WITH_SOURCE] relationships.") # Updated relationship name

    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
