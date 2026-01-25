import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class Neo4jManager:
    """
    Manages low-level Neo4j database operations and connection lifecycle.
    Provides generic query execution methods.
    """
    def __init__(self, uri: str, user: str, password: str):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None

    def __enter__(self):
        """Establishes connection and returns self for use in 'with' statements."""
        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self._driver.verify_connectivity() # Verify connection immediately
        logger.info(f"Neo4j connection established at {self.uri} with user {self.user}.")
        return self

    def __exit__(self, exc_type, exc, tb):
        """Closes the connection when exiting the 'with' block."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed.")

    def check_connection(self) -> bool:
        """Verifies connectivity to the Neo4j database."""
        try:
            if self._driver:
                self._driver.verify_connectivity()
                return True
            else:
                # Attempt to connect if not already connected
                with self: # Use __enter__ and __exit__
                    pass
                return True
        except Exception as e:
            logger.error(f"Neo4j connection check failed: {e}")
            return False

    def execute_read_query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a read-only Cypher query and returns a list of result records."""
        with self._driver.session() as session:
            result = session.run(cypher, parameters=params)
            return [record.data() for record in result]

    def execute_write_query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a write Cypher query and returns the summary counters."""
        with self._driver.session() as session:
            result = session.run(cypher, parameters=params)
            return result.consume().counters

    def get_schema(self) -> List[Dict[str, Any]]:
        """Retrieves the current schema of the Neo4j database."""
        with self._driver.session() as session:
            result = session.run("CALL db.schema.visualization()")
            return [record.data() for record in result]
            
