import logging
from typing import Dict, Any, Optional, List
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class ProjectSummarizer(BaseSummarizer):
    """
    Generates a summary for the single :Project node.
    """

    def __init__(
        self,
        neo4j_manager: Neo4jManager,
        node_summary_processor: NodeSummaryProcessor,
    ):
        super().__init__(neo4j_manager, node_summary_processor)

    def run(self) -> int:
        """
        Executes the project summarization pass.
        """
        logger.info(f"--- Starting Pass: {self.__class__.__name__} ---")

        items_to_process = self._get_project_with_context()
        if not items_to_process:
            logger.warning("No :Project node found to summarize. Skipping pass.")
            return 0

        updated_count = self.process_batch(items_to_process)
        logger.info(
            f"--- Pass {self.__class__.__name__} complete. "
            f"Updated {updated_count} properties. ---"
        )
        return updated_count

    def _get_project_with_context(self) -> List[Dict[str, Any]]:
        """
        Fetches the project node and the context of its direct children.
        """
        query = """
        MATCH (p:Project)
        // Gather context from top-level directories or packages
        OPTIONAL MATCH (p)-[:CONTAINS_SOURCE]->(child)
        RETURN
            p.entity_id AS id,
            p.name AS name,
            p.summary AS db_summary,
            collect(DISTINCT child.entity_id) AS dependency_ids
        LIMIT 1
        """
        return self.neo4j_manager.execute_read_query(query)

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (p:Project {entity_id: item.id})
        SET p.summary = item.summary
        """

    def _get_processor_result(
        self, item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return self.node_summary_processor.get_hierarchical_summary(
            item, "Project"
        )
