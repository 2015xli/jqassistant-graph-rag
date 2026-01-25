import argparse
import logging
import sys
from pathlib import Path

# Import modules from the same directory
from input_params import add_neo4j_args, add_logging_args, add_rag_args
from neo4j_manager import Neo4jManager
from log_manager import init_logging
from graph_orchestrator import GraphOrchestrator
from rag_orchestrator import RagOrchestrator

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="jQAssistant Graph RAG enrichment and analysis tool."
    )

    # Add argument groups
    add_neo4j_args(parser)
    add_logging_args(parser)
    add_rag_args(parser)

    args = parser.parse_args()

    init_logging(log_file=args.log_file, console_level=args.log_level.upper())

    # Extract Neo4j connection details
    uri, user, password = args.uri, args.user, args.password

    try:
        with Neo4jManager(uri=uri, user=user, password=password) as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                logger.critical("Failed to connect to Neo4j. Exiting.")
                sys.exit(1)

            try:
                # The orchestrator now determines the project path itself
                graph_orchestrator = GraphOrchestrator(neo4j_mgr)
                graph_orchestrator.run_enrichment_passes()

                if args.generate_summary:
                    # Pass the determined path to the RAG orchestrator
                    rag_orchestrator = RagOrchestrator(
                        neo4j_mgr,
                        graph_orchestrator.project_path,
                        args.llm_api
                    )
                    rag_orchestrator.run_rag_passes()
            except ValueError as e:
                logger.critical(f"Failed to initialize orchestrator: {e}")
                sys.exit(1)
            
    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
