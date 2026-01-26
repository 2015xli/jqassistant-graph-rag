import logging
from typing import Dict, Any, Optional, List
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager
from collections import defaultdict

logger = logging.getLogger(__name__)


class PackageSummarizer(BaseSummarizer):
    """
    Generates summaries for :Package nodes in a hierarchical, bottom-up manner.
    """

    def __init__(
        self,
        neo4j_manager: Neo4jManager,
        node_summary_processor: NodeSummaryProcessor,
    ):
        super().__init__(neo4j_manager, node_summary_processor)

    def run(self) -> int:
        """
        Executes the package summarization pass, processing packages level by level
        from deepest to shallowest.
        """
        logger.info(f"--- Starting Pass: {self.__class__.__name__} ---")

        all_packages_with_depth = self._get_packages_ordered_by_depth()
        if not all_packages_with_depth:
            logger.info("No packages found to process.")
            return 0

        # Group packages by depth
        packages_by_depth = defaultdict(list)
        for item in all_packages_with_depth:
            packages_by_depth[item['depth']].append(item)

        total_updated_count = 0
        # Process levels from deepest to shallowest
        for depth in sorted(packages_by_depth.keys(), reverse=True):
            items_at_current_depth = packages_by_depth[depth]
            logger.info(
                f"Processing {len(items_at_current_depth)} packages at depth {depth}."
            )
            updated_count = self.process_batch(items_at_current_depth)
            total_updated_count += updated_count

        logger.info(
            f"--- Pass {self.__class__.__name__} complete. "
            f"Updated {total_updated_count} summaries. ---"
        )
        return total_updated_count

    def _get_packages_ordered_by_depth(self) -> List[Dict[str, Any]]:
        """
        Fetches all packages, ordered from deepest to shallowest, along
        with the context of their direct children (types and sub-packages) and their depth.
        """
        query = """
        MATCH (p:Package)
        WHERE p.fqn IS NOT NULL
        WITH p, size(split(p.fqn, '.')) AS depth
        // Gather context from direct children
        OPTIONAL MATCH (p)-[:CONTAINS]->(child)
        WHERE child:Type OR child:Package
        RETURN
            p.entity_id AS id,
            p.fqn AS fqn,
            p.summary AS db_summary,
            collect(DISTINCT child.entity_id) AS dependency_ids,
            depth
        ORDER BY depth DESC
        """
        return self.neo4j_manager.execute_read_query(query)

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (p:Package {entity_id: item.id})
        SET p.summary = item.summary
        """

    def _get_processor_result(
        self, item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return self.node_summary_processor.get_hierarchical_summary(
            item, "Package"
        )
