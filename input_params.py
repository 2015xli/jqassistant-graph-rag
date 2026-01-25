import argparse
import os

def add_neo4j_args(parser: argparse.ArgumentParser):
    """Adds Neo4j connection arguments to the parser."""
    group = parser.add_argument_group("Neo4j Connection")
    group.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                       help="Neo4j connection URI (default: bolt://localhost:7687 or NEO4J_URI env var)")
    group.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"),
                       help="Neo4j username (default: neo4j or NEO4J_USER env var)")
    group.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "neo4j"),
                       help="Neo4j password (default: neo4j or NEO4J_PASSWORD env var)")

def add_logging_args(parser: argparse.ArgumentParser):
    """Adds logging related arguments to the parser."""
    group = parser.add_argument_group("Logging Configuration")
    group.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Set the console logging level (default: INFO)")
    group.add_argument("--log-file", default="debug.log",
                       help="Set the file for debug logging (default: debug.log). Only DEBUG messages are written here.")

def add_rag_args(parser: argparse.ArgumentParser):
    """Adds arguments related to RAG (summary and embedding) generation."""
    rag_group = parser.add_argument_group('RAG Generation (Optional)')
    rag_group.add_argument('--generate-summary', action='store_true',
                        help='Generate AI summaries and embeddings for the code graph.')
    rag_group.add_argument('--llm-api', choices=['openai', 'deepseek', 'ollama', 'fake'], default='fake',
                        help='The LLM API to use for summarization. (default fake)')
