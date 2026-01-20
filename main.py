import argparse
import logging
import sys
from pathlib import Path

# Import modules from the same directory
from input_params import add_neo4j_args, add_project_path_args, add_logging_args
from java_source_parser import JavaSourceParser
from kotlin_source_parser import KotlinSourceParser
from graph_enricher import GraphEnricher
from neo4j_manager import Neo4jManager
from log_manager import init_logging
from schema_analyzer import SchemaAnalyzer # New import

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="jQAssistant Graph RAG enrichment and analysis tool." # Updated description
    )

    # Add common arguments
    add_neo4j_args(parser)
    add_logging_args(parser)

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # Subparser for 'enrich' command
    enrich_parser = subparsers.add_parser("enrich", help="Enrich the jQAssistant graph with source code relationships.")
    add_project_path_args(enrich_parser) # Project path is specific to enrich

    # Subparser for 'analyze-schema' command
    analyze_parser = subparsers.add_parser("analyze-schema", help="Analyze and display the jQAssistant graph schema.")
    # No project_path needed for schema analysis, as it queries the DB directly

    args = parser.parse_args()

    init_logging(args.log_level)

    # Extract Neo4j connection details
    uri, user, password = args.uri, args.user, args.password
    #uri, user, password = "bolt://localhost:7688", "neo4j", "neo4j" # User's debug line

    try:
        with Neo4jManager(uri=uri, user=user, password=password) as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                logger.critical("Failed to connect to Neo4j. Exiting.")
                sys.exit(1)

            if args.command == "enrich":
                project_path = Path(args.project_path).resolve()
                if not project_path.is_dir():
                    logger.error(f"Error: Project path '{project_path}' is not a valid directory.")
                    sys.exit(1)
                
                logger.info(f"Starting jQAssistant Graph RAG enrichment for project: {project_path}")

                # Step 1: Parse Java and Kotlin source files
                all_source_metadata = []
                java_parser = JavaSourceParser(str(project_path))
                java_metadata = java_parser.parse_project()
                all_source_metadata.extend(java_metadata)

                try:
                    kotlin_parser = KotlinSourceParser(str(project_path))
                    kotlin_metadata = kotlin_parser.parse_project()
                    all_source_metadata.extend(kotlin_metadata)
                except ImportError as e:
                    logger.warning(f"Kotlin parsing skipped: {e}")
                except Exception as e:
                    logger.error(f"Error during Kotlin parsing: {e}")

                if not all_source_metadata:
                    logger.warning("No Java or Kotlin source files found or parsed. Exiting.")
                    sys.exit(0)

                # Step 2: Enrich Neo4j graph
                enricher = GraphEnricher(neo4j_manager=neo4j_mgr)
                relationships_created = enricher.enrich_graph(all_source_metadata)
                logger.info(f"Successfully created {relationships_created} new [:WITH_SOURCE] relationships.")
            
            elif args.command == "analyze-schema":
                analyzer = SchemaAnalyzer(neo4j_manager=neo4j_mgr)
                analyzer.analyze_schema()

    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
