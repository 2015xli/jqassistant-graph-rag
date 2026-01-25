import logging
import os
from typing import Optional, Dict, Any
from base_summarizer import BaseSummarizer
from node_summary_processor import NodeSummaryProcessor
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

class MethodAnalyzer(BaseSummarizer):
    """
    Analyzes code snippets for Method nodes by delegating to the NodeSummaryProcessor.
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
        MATCH (m:Method)-[:WITH_SOURCE]->(sf:SourceFile)
        WHERE m.firstLineNumber IS NOT NULL AND m.lastLineNumber IS NOT NULL
        RETURN m.entity_id AS id,
               sf.absolute_path AS sourceFilePath,
               m.firstLineNumber AS firstLine,
               m.lastLineNumber AS lastLine,
               m.code_analysis AS db_analysis,
               m.code_hash AS db_hash
        """

    def _get_update_query(self) -> str:
        return """
        UNWIND $updates AS item
        MATCH (m:Method {entity_id: item.id})
        SET m.code_analysis = item.code_analysis, m.code_hash = item.code_hash
        """

    def _prepare_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook to extract the method's source code before processing.
        """
        item['source_code'] = self._extract_method_code_snippet(
            item['sourceFilePath'], item['firstLine'], item['lastLine']
        )
        return item

    def _get_processor_result(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calls the appropriate method on the NodeSummaryProcessor.
        """
        return self.node_summary_processor.get_method_code_analysis(item)

    def _extract_method_code_snippet(self, file_path: str, first_line: int, last_line: int) -> Optional[str]:
        """
        Reads a source file and extracts the code snippet for a method.
        """
        try:
            if not os.path.isabs(file_path) or not os.path.exists(file_path):
                logger.error(f"Source file not found or path is not absolute: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            start_index = first_line - 1
            end_index = last_line

            if not (0 <= start_index < end_index <= len(lines)):
                logger.warning(f"Invalid line numbers for method in {file_path}: {first_line}-{last_line}. File has {len(lines)} lines.")
                return None
            
            return "".join(lines[start_index:end_index])
        except Exception as e:
            logger.error(f"Error extracting code snippet from {file_path}: {e}")
            return None
