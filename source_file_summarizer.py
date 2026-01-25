import logging
from typing import Dict, Any, Optional
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

class SourceFileSummarizer(BaseSummarizer):
    """
    Generates summaries for :SourceFile nodes by delegating to the NodeSummaryProcessor.
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
        MATCH (sf:SourceFile)
        OPTIONAL MATCH (sf)<-[:WITH_SOURCE]-(t:Type)
        WHERE t.summary IS NOT NULL
        RETURN sf.entity_id AS id,
               sf.absolute_path AS path,
               sf.summary AS db_summary,
               COLLECT(DISTINCT t.entity_id) AS dependency_ids
        """

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (sf:SourceFile {entity_id: item.id})
        SET sf.summary = item.summary
        """

    def _get_processor_result(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calls the appropriate method on the NodeSummaryProcessor.
        """
        return self.node_summary_processor.get_hierarchical_summary(item, 'SourceFile')
