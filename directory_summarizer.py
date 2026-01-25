import logging
from typing import Dict, Any, Optional, List
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class DirectorySummarizer(BaseSummarizer):
    """
    Generates summaries for :Directory nodes in a hierarchical, bottom-up manner.
    """

    def __init__(
        self,
        neo4j_manager: Neo4jManager,
        node_summary_processor: NodeSummaryProcessor,
    ):
        super().__init__(neo4j_manager, node_summary_processor)

    def run(self) -> int:
        """
        Executes the directory summarization pass.
        """
        logger.info(f"--- Starting Pass: {self.__class__.__name__} ---")

        items_to_process = self._get_directories_ordered_by_depth()
        if not items_to_process:
            logger.info("No directories found to process.")
            return 0

        logger.info(f"Found {len(items_to_process)} directories to process.")
        updated_count = self.process_batch(items_to_process)

        logger.info(
            f"--- Pass {self.__class__.__name__} complete. "
            f"Updated {updated_count} summaries. ---"
        )
        return updated_count

    def _get_directories_ordered_by_depth(self) -> List[Dict[str, Any]]:
        """
        Fetches all directories, ordered from deepest to shallowest, along
        with the context of their direct children.
        """
        query = """
        MATCH (d:Directory)
        WHERE d.absolute_path IS NOT NULL
        // Order by path depth to process deepest directories first
        WITH d ORDER BY size(split(d.absolute_path, '/')) DESC
        // Gather context from direct children
        OPTIONAL MATCH (d)-[:CONTAINS_SOURCE]->(child)
        WHERE child:SourceFile OR child:Directory
        RETURN
            d.entity_id AS id,
            d.absolute_path AS path,
            d.summary AS db_summary,
            collect(DISTINCT child.entity_id) AS dependency_ids
        """
        return self.neo4j_manager.execute_read_query(query)

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (d:Directory {entity_id: item.id})
        SET d.summary = item.summary
        """

    def _get_processor_result(
        self, item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return self.node_summary_processor.get_hierarchical_summary(
            item, "Directory"
        )
