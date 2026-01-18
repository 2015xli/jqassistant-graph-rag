import argparse
import os

def add_neo4j_args(parser: argparse.ArgumentParser):
    """Adds Neo4j connection arguments to the parser."""
    group = parser.add_argument_group("Neo4j Connection")
    group.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7688"),
                       help="Neo4j connection URI (default: bolt://localhost:7688 or NEO4J_URI env var)")
    group.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"),
                       help="Neo4j username (default: neo4j or NEO4J_USER env var)")
    group.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "neo4j"),
                       help="Neo4j password (default: neo4j or NEO4J_PASSWORD env var)")

def add_project_path_args(parser: argparse.ArgumentParser):
    """Adds project path argument to the parser."""
    group = parser.add_argument_group("Project Configuration")
    group.add_argument("project_path", type=str,
                       help="The root path of the Java project to scan.")

def add_logging_args(parser: argparse.ArgumentParser):
    """Adds logging related arguments to the parser."""
    group = parser.add_argument_group("Logging Configuration")
    group.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Set the logging level (default: INFO)")
