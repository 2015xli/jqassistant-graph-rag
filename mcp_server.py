import os, argparse, logging, re
from typing import Optional, Dict, Any

from fastmcp import FastMCP
from neo4j_manager import Neo4jManager
from llm_client import get_embedding_client

# --- Configuration and Initialization ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

mcp = FastMCP()

# Globals to be initialized on startup
neo4j_mgr: Optional[Neo4jManager] = None
project_root_path: Optional[str] = None
embedding_client = get_embedding_client("sentence-transformer")

# --- Helper Functions ---
def _initialize_managers(uri, user, password):
    """Initializes Neo4j connection and discovers project root path."""
    global neo4j_mgr, project_root_path
    if neo4j_mgr is None:
        neo4j_mgr = Neo4jManager(uri, user, password)
        if not neo4j_mgr.check_connection():
            logger.critical("Failed to connect to Neo4j. Exiting.")
            raise ConnectionError("Failed to connect to Neo4j.")
        
        query = "MATCH (p:Project) RETURN p.absolute_path AS path"
        result = neo4j_mgr.execute_read_query(query)
        if result and result[0] and result[0].get('path'):
            project_root_path = result[0]['path']
            logger.info(f"Discovered project root: {project_root_path}")
        else:
            logger.critical("Could not determine project root path from Neo4j.")
            raise ValueError("Project root path not found in Neo4j.")
        
        logger.info("Graph is assumed to contain embeddings. Semantic search is enabled.")

def _read_file_slice(file_path: str, start_line: int, end_line: int) -> str:
    """Reads a specific 1-based line range from a file."""
    try:
        with open(file_path, 'r', errors='ignore') as f:
            lines = f.readlines()
        # Adjust for 0-based indexing of list slicing
        code_lines = lines[start_line - 1 : end_line]
        return "".join(code_lines)
    except Exception as e:
        logger.error(f"Error reading file slice {file_path} lines {start_line}-{end_line}: {e}")
        return f"Error reading file: {e}"

# --- FastMCP Tools ---

@mcp.tool(name="get_graph_schema", description="Retrieves the curated graph schema to understand node properties and relationships.")
def get_graph_schema() -> str:
    """
    Retrieves the content of the mcp_visible_neo4j_schema.txt file.
    """
    schema_file_path = os.path.join(os.path.dirname(__file__), "mcp_visible_neo4j_schema.txt")
    if os.path.isfile(schema_file_path):
        try:
            with open(schema_file_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading graph schema file: {e}")
            return f"Error: Could not read graph schema file: {e}"
    else: 
        return "Error: The curated schema file 'mcp_visible_neo4j_schema.txt' was not found."

@mcp.tool(name="get_project_info", description="Retrieves the project's name, root path, and high-level summary.")
def get_project_info() -> Dict[str, str]:
    """Queries the Neo4j database for the project's name, root path, and summary."""
    try:
        query = "MATCH (p:Project) RETURN p.name AS name, p.absolute_path AS path, p.summary AS summary"
        result = neo4j_mgr.execute_read_query(query)
        if result and result[0]:
            return {
                "name": result[0].get('name', 'N/A'), 
                "path": result[0].get('path', 'N/A'), 
                "summary": result[0].get("summary") or "No project summary available."
            }
        return {"error": "No :Project node found in the graph."}
    except Exception as e:
        return {"error": f"Could not retrieve project info: {e}"}

@mcp.tool(name="get_source_code_by_id", description="Retrieves source code for a node (Method, Class, SourceFile, etc.) by its unique entity_id.")
def get_source_code_by_id(entity_id: str) -> Dict[str, str]:
    """
    Retrieves source code for a given entity_id. For Methods, it returns the specific
    body. For other types, it returns the entire source file content.
    """
    try:
        query = """
        MATCH (n) WHERE n.entity_id = $entity_id
        OPTIONAL MATCH (n)-[:WITH_SOURCE]->(sf:SourceFile)
        RETURN
            labels(n) AS labels,
            n.firstLineNumber AS start_line,
            n.lastLineNumber AS end_line,
            // If the node is a SourceFile itself, its path is the source path
            CASE WHEN 'SourceFile' IN labels(n) THEN n.absolute_path ELSE sf.absolute_path END AS file_path
        """
        result = neo4j_mgr.execute_read_query(query, {"entity_id": entity_id})

        if not result or not result[0]:
            return {"id": entity_id, "source_code": "Error: Node not found."}

        node_info = result[0]
        labels = node_info.get('labels', [])
        file_path = node_info.get('file_path')

        if not file_path:
            return {"id": entity_id, "source_code": "Error: Node has no associated source file."}
        
        if not os.path.exists(file_path):
            return {"id": entity_id, "source_code": f"Error: File not found on disk: {file_path}"}

        start_line = node_info.get('start_line')
        end_line = node_info.get('end_line')

        if 'Method' in labels and start_line and end_line:
            source_code = _read_file_slice(file_path, start_line, end_line)
        else:
            with open(file_path, 'r', errors='ignore') as f:
                source_code = f.read()
        
        return {"id": entity_id, "source_code": source_code}
    except Exception as e:
        return {"id": entity_id, "source_code": f"Error: Could not retrieve source code: {e}"}

@mcp.tool(name="execute_cypher_query", description="Executes a read-only Cypher query against the graph.")
def execute_cypher_query(query: str) -> Dict[str, Any]:
    """Executes a read-only Cypher query and returns the results as a list of dictionaries."""
    read_only_keywords = ['MATCH', 'OPTIONAL MATCH', 'WHERE', 'RETURN', 'UNWIND', 'CALL', 'WITH']
    if not any(re.search(r'\b' + keyword + r'\b', query, re.IGNORECASE) for keyword in read_only_keywords):
        return {"error": "Query must contain a read-only keyword."}

    write_keywords = ['CREATE', 'SET', 'DELETE', 'MERGE', 'REMOVE', 'DETACH']
    if any(re.search(r'\b' + keyword + r'\b', query, re.IGNORECASE) for keyword in write_keywords):
        return {"error": "Write operations are not allowed."}

    try:
        results = neo4j_mgr.execute_read_query(query)
        return {"results": [dict(record) for record in results]}
    except Exception as e:
        return {"error": f"Could not execute query: {e}"}

@mcp.tool(name="generate_embeddings", description="Generates vector embeddings for a query string.")
def generate_embeddings(query: str) -> list[float]:
    """Generates vector embeddings for a query string for semantic search."""
    embeddings = embedding_client.generate_embeddings([query], show_progress_bar=False)
    return embeddings[0] if embeddings else []

@mcp.tool(name="search_nodes_for_semantic_similarity", description="Performs a semantic similarity search across nodes in the graph.")
def search_nodes_for_semantic_similarity(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Performs a vector similarity search on node summaries."""
    try:
        embedding = generate_embeddings(query)
        if not embedding:
            return {"error": "Failed to generate embedding for the query."}

        cypher_query = """
            CALL db.index.vector.queryNodes('summaryEmbeddings', $num_results, $embedding)
            YIELD node, score
            RETURN 
                node.entity_id AS id, 
                coalesce(node.fqn, node.name, node.absolute_path) AS name, 
                labels(node) AS labels, 
                node.summary AS summary, 
                score
            ORDER BY score DESC
        """
        params = {"num_results": num_results, "embedding": embedding}
        results = neo4j_mgr.execute_read_query(cypher_query, params)
        return {"results": results}
    except Exception as e:
        return {"error": f"An error occurred during semantic search: {e}"}

# --- FastMCP Application ---
if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="Start the FastMCP server for jqassistant-graph-rag.")
    parser.add_argument("--uri", default="bolt://localhost:7688", help="Neo4j Bolt URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo4j", help="Neo4j password")
    args = parser.parse_args()

    logger.info("Starting FastMCP server for jqassistant-graph-rag...")
    _initialize_managers(args.uri, args.user, args.password)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8800)
    if neo4j_mgr:
        neo4j_mgr.close()
