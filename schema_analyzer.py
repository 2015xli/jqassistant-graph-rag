import argparse
import logging
import sys
from typing import List, Dict, Any
from neo4j_manager import Neo4jManager
from input_params import add_neo4j_args, add_logging_args
from log_manager import init_logging

logger = logging.getLogger(__name__)


class SchemaAnalyzer:
    """
    Provides methods to analyze and display the jQAssistant graph schema.
    """

    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized SchemaAnalyzer.")

    def list_node_labels_and_counts(self) -> List[Dict[str, Any]]:
        """Lists all node labels in the graph and their counts."""
        query = """
        CALL db.labels() YIELD label
        MATCH (n)
        WHERE label IN labels(n)
        RETURN label, count(n) AS count
        ORDER BY count DESC
        """
        logger.info("Listing node labels and counts...")
        return self.neo4j_manager.execute_read_query(query)

    def list_relationship_types_and_counts(self) -> List[Dict[str, Any]]:
        """Lists all relationship types in the graph and their counts."""
        query = """
        CALL db.relationshipTypes() YIELD relationshipType
        MATCH ()-[r]->()
        WHERE type(r) = relationshipType
        RETURN relationshipType, count(r) AS count
        ORDER BY count DESC
        """
        logger.info("Listing relationship types and counts...")
        return self.neo4j_manager.execute_read_query(query)

    def analyze_schema(self):
        """Executes all schema analysis queries and prints the results."""
        print("\n--- Starting jQAssistant Schema Analysis ---")

        print("\nNode Labels and Counts:")
        labels_counts = self.list_node_labels_and_counts()
        if not labels_counts:
            print("  No node labels found.")
        for item in labels_counts:
            print(f"  - {item['label']}: {item['count']}")

        print("\nRelationship Types and Counts:")
        rel_counts = self.list_relationship_types_and_counts()
        if not rel_counts:
            print("  No relationship types found.")
        for item in rel_counts:
            print(f"  - {item['relationshipType']}: {item['count']}")

        print("\n--- jQAssistant Schema Analysis Complete ---")


def main():
    parser = argparse.ArgumentParser(
        description="jQAssistant Graph Schema Analysis Tool."
    )
    add_neo4j_args(parser)
    add_logging_args(parser)
    args = parser.parse_args()

    init_logging(log_file=args.log_file, console_level=args.log_level.upper())

    try:
        with Neo4jManager(
            uri=args.uri, user=args.user, password=args.password
        ) as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                logger.critical("Failed to connect to Neo4j. Exiting.")
                sys.exit(1)

            analyzer = SchemaAnalyzer(neo4j_mgr)
            analyzer.analyze_schema()

    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
