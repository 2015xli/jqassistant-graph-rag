import logging
from collections import defaultdict
from typing import Dict, Any, Optional, List
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class TypeSummarizer(BaseSummarizer):
    """
    Generates summaries for :Type nodes by respecting the inheritance and
    composition hierarchy. It first computes the inheritance hierarchy for all
    source-linked types and then processes them level by level, from base
    types to derived types.
    """

    def __init__(
        self,
        neo4j_manager: Neo4jManager,
        node_summary_processor: NodeSummaryProcessor,
    ):
        super().__init__(neo4j_manager, node_summary_processor)

    def run(self) -> int:
        """
        Orchestrates the type summarization by processing types in batches
        based on their level in the inheritance hierarchy.
        """
        logger.info(f"--- Starting Pass: {self.__class__.__name__} ---")

        types_by_level = self._get_types_by_inheritance_level()
        if not types_by_level:
            logger.info("No source-linked types found to process.")
            return 0

        total_updated_count = 0
        for level in sorted(types_by_level.keys()):
            level_ids = types_by_level[level]
            logger.info(
                f"Processing {len(level_ids)} types at inheritance level {level}."
            )

            # Fetch the full context for all types at the current level
            items_to_process = self._get_context_for_ids(level_ids)
            if not items_to_process:
                continue

            updated_count = self.process_batch(items_to_process)
            total_updated_count += updated_count

        logger.info(
            f"--- Pass {self.__class__.__name__} complete. "
            f"Updated {total_updated_count} summaries in total. ---"
        )
        return total_updated_count

    def _get_types_by_inheritance_level(self) -> Dict[int, List[str]]:
        """
        Determines the processing order of types by grouping them into levels
        based on their inheritance hierarchy.
        Returns:
            A dictionary mapping level number to a list of element IDs.
        """
        # 1. Get all types that are defined in the project's source files
        query_all = """
        MATCH (t:Type)-[:WITH_SOURCE]->(:SourceFile)
        WHERE t:Class OR t:Interface OR t:Enum OR t:Record
        RETURN t.entity_id AS id
        """
        result = self.neo4j_manager.execute_read_query(query_all)
        all_source_type_ids = {r["id"] for r in result}
        if not all_source_type_ids:
            return {}

        # 2. Find Level 0: Types that do not inherit from any other source type
        query_level_0 = """
        MATCH (t:Type)
        WHERE t.entity_id IN $ids
        AND NOT (t)-[:EXTENDS|IMPLEMENTS]->(:Type)-[:WITH_SOURCE]->()
        RETURN t.entity_id AS id
        """
        result = self.neo4j_manager.execute_read_query(
            query_level_0, params={"ids": list(all_source_type_ids)}
        )
        
        types_by_level = defaultdict(list)
        visited_ids = set()
        
        if result:
            level_0_ids = [r["id"] for r in result]
            types_by_level[0] = level_0_ids
            visited_ids.update(level_0_ids)

        # 3. Iteratively find subsequent levels
        current_level = 0
        while True:
            level_nodes = types_by_level.get(current_level, [])
            if not level_nodes:
                break  # No more nodes to process

            current_level += 1
            query_next_level = """
            MATCH (t:Type)
            WHERE t.entity_id IN $all_ids AND NOT t.entity_id IN $visited_ids
            // Get all source-linked parents
            WITH t, [
                (t)-[:EXTENDS|IMPLEMENTS]->(p:Type)
                WHERE p.entity_id IN $all_ids | p
            ] AS parents
            // A type is in the next level if all its source-linked parents
            // have already been visited (i.e., are in previous levels).
            WHERE size(parents) > 0 AND all(p IN parents WHERE p.entity_id IN $visited_ids)
            RETURN t.entity_id AS id
            """
            result = self.neo4j_manager.execute_read_query(
                query_next_level,
                params={
                    "all_ids": list(all_source_type_ids),
                    "visited_ids": list(visited_ids),
                },
            )
            
            if result:
                next_level_ids = [r["id"] for r in result]
                if not next_level_ids:
                    break # No new nodes found
                types_by_level[current_level] = next_level_ids
                visited_ids.update(next_level_ids)
            else:
                break
        
        return dict(types_by_level)

    def _get_context_for_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches the full context needed for summarization for a given list of
        type element IDs.
        """
        query = """
        MATCH (t:Type)
        WHERE t.entity_id IN $ids
        OPTIONAL MATCH (t)-[:EXTENDS|IMPLEMENTS]->(p:Type)
        WITH t, COLLECT(DISTINCT p.entity_id) AS parent_ids
        OPTIONAL MATCH (t)-[:DECLARES]->(m)
        WHERE m:Method OR m:Field
        WITH t, parent_ids, COLLECT(DISTINCT m.entity_id) AS member_ids
        RETURN
            t.entity_id AS id,
            t.name AS name,
            t.summary AS db_summary,
            labels(t) AS labels,
            parent_ids,
            member_ids
        """
        return self.neo4j_manager.execute_read_query(query, params={"ids": ids})

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (t:Type)
        WHERE t.entity_id = item.id
        SET t.summary = item.summary
        """

    def _prepare_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        type_label_candidates = [
            label
            for label in item["labels"]
            if label in ["Class", "Interface", "Enum", "Record"]
        ]
        item["label"] = (
            type_label_candidates[0] if type_label_candidates else "Type"
        )
        return item

    def _get_processor_result(
        self, item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return self.node_summary_processor.get_type_summary(item)
