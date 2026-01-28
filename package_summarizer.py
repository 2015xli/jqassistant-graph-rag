import logging
from typing import Dict, Any, Optional, List
from collections import defaultdict
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class PackageSummarizer(BaseSummarizer):
    """
    Generates summaries for :Package and :ClassTree nodes in a hierarchical,
    bottom-up manner using the [:CONTAINS_CLASS] relationship.
    """

    def __init__(
        self,
        neo4j_manager: Neo4jManager,
        node_summary_processor: NodeSummaryProcessor,
    ):
        super().__init__(neo4j_manager, node_summary_processor)

    def run(self) -> int:
        """
        Executes the package summarization pass in two phases:
        1. Summarize internal packages from the bottom up.
        2. Summarize the ClassTree roots themselves.
        """
        logger.info(f"--- Starting Pass: {self.__class__.__name__} ---")
        total_updated_count = 0

        # Phase 1: Summarize internal packages
        updated_in_phase1 = self._summarize_internal_packages()
        total_updated_count += updated_in_phase1

        # Phase 2: Summarize ClassTree roots
        updated_in_phase2 = self._summarize_class_tree_roots()
        total_updated_count += updated_in_phase2

        logger.info(
            f"--- Pass {self.__class__.__name__} complete. "
            f"Updated {total_updated_count} summaries. ---"
        )
        return total_updated_count

    def _summarize_internal_packages(self) -> int:
        """Processes all :Package nodes within :ClassTree containers."""
        logger.info("Phase 1: Summarizing internal packages.")
        query = """
        MATCH (ct:ClassTree)-[:CONTAINS_CLASS*]->(p:Package)
        WHERE p.fqn IS NOT NULL AND p.summary IS NULL
        WITH p, size(split(p.fqn, '.')) AS depth
        OPTIONAL MATCH (p)-[:CONTAINS_CLASS]->(child)
        WHERE child:Package OR child:Type
        RETURN
            p.entity_id AS id,
            p.fqn AS fqn,
            p.summary AS db_summary,
            collect(DISTINCT child.entity_id) AS dependency_ids,
            depth
        ORDER BY depth DESC
        """
        items_to_process = self.neo4j_manager.execute_read_query(query)
        
        if not items_to_process:
            logger.info("No internal packages to summarize.")
            return 0

        # Group by depth to process bottom-up
        items_by_depth = defaultdict(list)
        for item in items_to_process:
            items_by_depth[item['depth']].append(item)

        updated_count = 0
        for depth in sorted(items_by_depth.keys(), reverse=True):
            batch = items_by_depth[depth]
            logger.info(f"Processing {len(batch)} internal packages at depth {depth}.")
            updated_count += self.process_batch(batch)
        
        return updated_count

    def _summarize_class_tree_roots(self) -> int:
        """Processes the root :ClassTree nodes."""
        logger.info("Phase 2: Summarizing ClassTree roots.")
        query = """
        MATCH (ct:ClassTree)
        WHERE ct.summary IS NULL
        OPTIONAL MATCH (ct)-[:CONTAINS_CLASS]->(child)
        WHERE child:Package OR child:Type
        RETURN
            ct.entity_id AS id,
            ct.fileName AS path,
            ct.summary AS db_summary,
            collect(DISTINCT child.entity_id) AS dependency_ids
        """
        items_to_process = self.neo4j_manager.execute_read_query(query)

        if not items_to_process:
            logger.info("No ClassTree roots to summarize.")
            return 0
        
        return self.process_batch(items_to_process)

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (p)
        WHERE p.entity_id = item.id
        SET p.summary = item.summary
        """

    def _get_processor_result(
        self, item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        # Use "Package" as the generic node type for the prompt, which works for both
        return self.node_summary_processor.get_hierarchical_summary(
            item, "Package"
        )