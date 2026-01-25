import logging
from typing import Dict, Any, Optional
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

class MethodSummarizer(BaseSummarizer):
    """
    Generates contextual summaries for Method nodes by delegating to the NodeSummaryProcessor.
    """
    def __init__(self, neo4j_manager: Neo4jManager, node_summary_processor: NodeSummaryProcessor):
        super().__init__(neo4j_manager, node_summary_processor)

    def run(self) -> int:
        logger.info(f"--- Starting Pass: {self.__class__.__name__} ---")
        items_to_process = self.neo4j_manager.execute_read_query(self._get_items_query())
        
        if not items_to_process:
            logger.warning(f"No items found for {self.__class__.__name__}. Skipping pass.")
            return 0
            
        updated_count = self.process_batch(items_to_process)
        logger.info(f"--- Pass {self.__class__.__name__} complete. Updated {updated_count} properties. ---")
        return updated_count

    def _get_items_query(self) -> str:
        return """
        MATCH (m:Method)
        WHERE m.code_analysis IS NOT NULL
        OPTIONAL MATCH (caller:Method)-[:INVOKES]->(m)
        OPTIONAL MATCH (m)-[:INVOKES]->(callee:Method)
        RETURN m.entity_id AS id,
               m.name AS name,
               m.summary AS db_summary,
               collect(DISTINCT caller.name) AS callers,
               collect(DISTINCT callee.name) AS callees
        """

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (m:Method {entity_id: item.id})
        SET m.summary = item.summary
        """

    def _get_processor_result(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calls the appropriate method on the NodeSummaryProcessor.
        """
        return self.node_summary_processor.get_method_summary(item)
