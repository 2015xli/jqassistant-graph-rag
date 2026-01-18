import argparse
import logging
import sys
from pathlib import Path

# Import modules from the same directory
from input_params import add_neo4j_args, add_project_path_args, add_logging_args
from java_source_parser import JavaSourceParser
from graph_enricher import GraphEnricher # Updated import
from neo4j_manager import Neo4jManager # New import
from log_manager import init_logging # Import the new init_logging

logger = logging.getLogger(__name__) # Keep this for main.py's own logging

def main():
    parser = argparse.ArgumentParser(
        description="Enrich a jQAssistant Neo4j graph by connecting Java source files to Type:Class nodes."
    )

    add_project_path_args(parser)
    add_neo4j_args(parser)
    add_logging_args(parser)

    args = parser.parse_args()

    # Initialize logging based on parsed arguments
    init_logging(args.log_level)

    # Resolve project path
    project_path = Path(args.project_path).resolve()
    if not project_path.is_dir():
        logger.error(f"Error: Project path '{project_path}' is not a valid directory.")
        sys.exit(1)
    
    logger.info(f"Starting jQAssistant Graph RAG enrichment for project: {project_path}")

    try:
        # Step 1: Parse Java source files
        java_parser = JavaSourceParser(str(project_path))
        source_metadata = java_parser.parse_project()

        if not source_metadata:
            logger.warning("No Java source files found or parsed. Exiting.")
            sys.exit(0)

        # Step 2: Enrich Neo4j graph
        # Instantiate Neo4jManager and pass it to GraphEnricher
        with Neo4jManager(uri=args.uri, user=args.user, password=args.password) as neo4j_mgr:
            enricher = GraphEnricher(neo4j_manager=neo4j_mgr) # Pass manager instance
            relationships_created = enricher.enrich_graph(source_metadata)
            logger.info(f"Successfully created {relationships_created} new [:WITH_SOURCE] relationships.") # Updated relationship name

    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
