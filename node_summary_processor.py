import hashlib
import logging
from typing import Any, Dict, List, Optional

from llm_client import LlmClient
from prompt_manager import PromptManager
from summary_cache_manager import SummaryCacheManager
from token_manager import TokenManager

logger = logging.getLogger(__name__)


class NodeSummaryProcessor:
    """
    Stateless logic layer for processing a single node to generate a summary.
    Encapsulates the waterfall decision process: DB -> Cache -> LLM.
    It is responsible for deciding if a summary needs to be regenerated and
    orchestrating the generation process, including handling large contexts
    that require iterative summarization.
    """

    def __init__(
        self,
        llm_client: LlmClient,
        cache_manager: SummaryCacheManager,
    ):
        self.llm_client = llm_client
        self.cache_manager = cache_manager
        
        # Instantiate internal, stateless dependencies
        self.prompt_manager = PromptManager()
        self.token_manager = TokenManager()

    def get_method_code_analysis(
        self, node_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a method for code analysis using a content hash.
        If the source code is too large, it is chunked and analyzed iteratively.
        """
        node_id = node_data["id"]
        source_code = node_data.get("source_code")
        if not source_code:
            return None

        new_hash = hashlib.md5(source_code.encode("utf-8")).hexdigest()
        db_analysis = node_data.get("db_analysis")
        db_hash = node_data.get("db_hash")

        # 1. Check DB state (perfect hit)
        if db_analysis and db_hash == new_hash:
            return {
                "status": "unchanged",
                "id": node_id,
                "code_analysis": db_analysis,
                "code_hash": new_hash,
            }

        # 2. Check Cache state (restorable)
        cached_node = self.cache_manager.get_node_cache(node_id)
        if (
            cached_node.get("code_hash") == new_hash
            and cached_node.get("code_analysis")
        ):
            return {
                "status": "restored",
                "id": node_id,
                "code_analysis": cached_node["code_analysis"],
                "code_hash": new_hash,
            }

        # 3. Regenerate
        new_analysis = self._analyze_code_iteratively(source_code)
        if new_analysis:
            return {
                "status": "regenerated",
                "id": node_id,
                "code_analysis": new_analysis,
                "code_hash": new_hash,
            }

        return None

    def _analyze_code_iteratively(self, source_code: str) -> Optional[str]:
        """
        Analyzes a block of source code, chunking it if necessary.
        """
        token_count = self.token_manager.get_token_count(source_code)
        if token_count <= self.token_manager.max_context_token_size:
            chunks = [source_code]
        else:
            logger.info(
                f"Source code is large ({token_count} tokens), chunking..."
            )
            chunks = self.token_manager.chunk_text_by_tokens(source_code)

        running_summary = ""
        for i, chunk in enumerate(chunks):
            prompt = self.prompt_manager.get_method_analysis_prompt(
                chunk,
                is_first_chunk=(i == 0),
                is_last_chunk=(i == len(chunks) - 1),
                running_summary=running_summary,
            )
            new_summary = self.llm_client.generate_summary(prompt)
            if not new_summary:
                logger.error(
                    f"Iterative code analysis failed at chunk {i + 1}."
                )
                return None
            running_summary = new_summary

        return running_summary

    def get_method_summary(
        self, node_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a method for a contextual summary. Handles large context
        from callers and callees through iterative refinement.
        """
        node_id = node_data["id"]
        db_summary = node_data.get("db_summary")

        is_stale = self.cache_manager.was_dependency_changed([node_id])

        # 1. Check DB state
        if db_summary and not is_stale:
            return {"status": "unchanged", "id": node_id, "summary": db_summary}

        # 2. Check Cache state
        cached_summary = self.cache_manager.get_node_cache(node_id).get(
            "summary"
        )
        if cached_summary and not is_stale:
            return {"status": "restored", "id": node_id, "summary": cached_summary}

        # 3. Regenerate
        code_analysis = self.cache_manager.get_node_cache(node_id).get(
            "code_analysis"
        )
        if not code_analysis:
            return None  # Cannot proceed without code analysis

        # Fetch caller and callee summaries from the cache
        caller_summaries = [
            self.cache_manager.get_node_cache(dep_id).get("summary")
            for dep_id in node_data.get("callers", [])
        ]
        caller_summaries = [s for s in caller_summaries if s]

        callee_summaries = [
            self.cache_manager.get_node_cache(dep_id).get("summary")
            for dep_id in node_data.get("callees", [])
        ]
        callee_summaries = [s for s in callee_summaries if s]

        # Check if the total context fits into a single prompt
        full_context = " ".join([code_analysis] + caller_summaries + callee_summaries)
        if (
            self.token_manager.get_token_count(full_context)
            < self.token_manager.max_context_token_size
        ):
            prompt = self.prompt_manager.get_method_summary_prompt(
                node_data["name"],
                code_analysis,
                caller_summaries,
                callee_summaries,
            )
            new_summary = self.llm_client.generate_summary(prompt)
        else:
            logger.info(
                f"Context for method '{node_data['name']}' is too large, "
                "starting iterative summarization..."
            )
            new_summary = self._summarize_method_context_iteratively(
                code_analysis, caller_summaries, callee_summaries
            )

        if new_summary:
            return {
                "status": "regenerated",
                "id": node_id,
                "summary": new_summary,
            }

        return None

    def _summarize_method_context_iteratively(
        self,
        code_analysis: str,
        caller_summaries: List[str],
        callee_summaries: List[str],
    ) -> Optional[str]:
        """
        Generates a method summary by iteratively folding in caller and
        callee context.
        """
        # Start with the code analysis as the base summary
        running_summary = code_analysis

        # Iteratively fold in caller context
        caller_chunks = self.token_manager.chunk_summaries_by_tokens(
            caller_summaries
        )
        for i, chunk in enumerate(caller_chunks):
            prompt = self.prompt_manager.get_iterative_method_summary_prompt(
                running_summary, chunk, "callers"
            )
            new_summary = self.llm_client.generate_summary(prompt)
            if not new_summary:
                logger.error(
                    f"Iterative method summary (callers) failed at chunk {i+1}."
                )
                return None
            running_summary = new_summary

        # Iteratively fold in callee context
        callee_chunks = self.token_manager.chunk_summaries_by_tokens(
            callee_summaries
        )
        for i, chunk in enumerate(callee_chunks):
            prompt = self.prompt_manager.get_iterative_method_summary_prompt(
                running_summary, chunk, "callees"
            )
            new_summary = self.llm_client.generate_summary(prompt)
            if not new_summary:
                logger.error(
                    f"Iterative method summary (callees) failed at chunk {i+1}."
                )
                return None
            running_summary = new_summary

        return running_summary

    def get_type_summary(
        self, node_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a type for a contextual summary. Handles large context
        from parent types and child members through iterative refinement.
        """
        node_id = node_data["id"]
        db_summary = node_data.get("db_summary")
        parent_ids = node_data.get("parent_ids", [])
        member_ids = node_data.get("member_ids", [])
        dependency_ids = parent_ids + member_ids

        is_stale = self.cache_manager.was_dependency_changed(dependency_ids)

        # 1. Check DB state
        if db_summary and not is_stale:
            return {"status": "unchanged", "id": node_id, "summary": db_summary}

        # 2. Check Cache state
        cached_summary = self.cache_manager.get_node_cache(node_id).get("summary")
        if cached_summary and not is_stale:
            return {"status": "restored", "id": node_id, "summary": cached_summary}

        # 3. Regenerate
        parent_summaries = [
            self.cache_manager.get_node_cache(dep_id).get("summary")
            for dep_id in parent_ids
        ]
        parent_summaries = [s for s in parent_summaries if s]

        member_summaries = [
            self.cache_manager.get_node_cache(dep_id).get("summary")
            for dep_id in member_ids
        ]
        member_summaries = [s for s in member_summaries if s]

        # Check if the total context fits into a single prompt
        full_context = " ".join(parent_summaries + member_summaries)
        if (
            self.token_manager.get_token_count(full_context)
            < self.token_manager.max_context_token_size
        ):
            prompt = self.prompt_manager.get_type_summary_prompt(
                node_data["name"],
                node_data["label"],
                parent_summaries,
                member_summaries,
            )
            new_summary = self.llm_client.generate_summary(prompt)
        else:
            logger.info(
                f"Context for type '{node_data['name']}' is too large, "
                "starting iterative summarization..."
            )
            new_summary = self._summarize_type_context_iteratively(
                node_data, parent_summaries, member_summaries
            )

        if new_summary:
            return {"status": "regenerated", "id": node_id, "summary": new_summary}

        return None

    def _summarize_hierarchical_iteratively(
        self,
        node_data: Dict[str, Any],
        node_type: str,
        child_summaries: List[str],
    ) -> Optional[str]:
        """
        Generates a hierarchical summary by iteratively folding in child context.
        """
        node_name = (
            node_data.get("path")
            or node_data.get("fqn")
            or node_data.get("name")
        )
        running_summary = (
            f"A {node_type} named '{node_name}' that serves a purpose to be defined by its contents."
        )

        child_chunks = self.token_manager.chunk_summaries_by_tokens(
            child_summaries
        )
        for i, chunk in enumerate(child_chunks):
            prompt = self.prompt_manager.get_iterative_hierarchical_prompt(
                node_type, node_name, running_summary, chunk
            )
            new_summary = self.llm_client.generate_summary(prompt)
            if not new_summary:
                logger.error(
                    f"Iterative hierarchical summary for {node_type} '{node_name}' "
                    f"failed at chunk {i+1}."
                )
                return None
            running_summary = new_summary

        return running_summary

    def _summarize_type_context_iteratively(
        self,
        node_data: Dict[str, Any],
        parent_summaries: List[str],
        member_summaries: List[str],
    ) -> Optional[str]:
        """
        Generates a type summary by iteratively folding in parent and
        member context.
        """
        type_name = node_data["name"]
        type_label = node_data["label"]
        running_summary = (
            f"A {type_label} named '{type_name}' that serves a purpose to be defined by its relationships."
        )

        # Iteratively fold in parent context
        parent_chunks = self.token_manager.chunk_summaries_by_tokens(parent_summaries)
        for i, chunk in enumerate(parent_chunks):
            prompt = self.prompt_manager.get_iterative_type_summary_prompt(
                type_name, type_label, running_summary, chunk, "parents"
            )
            new_summary = self.llm_client.generate_summary(prompt)
            if not new_summary:
                logger.error(
                    f"Iterative type summary (parents) failed at chunk {i+1}."
                )
                return None
            running_summary = new_summary

        # Iteratively fold in member context
        member_chunks = self.token_manager.chunk_summaries_by_tokens(member_summaries)
        for i, chunk in enumerate(member_chunks):
            prompt = self.prompt_manager.get_iterative_type_summary_prompt(
                type_name, type_label, running_summary, chunk, "members"
            )
            new_summary = self.llm_client.generate_summary(prompt)
            if not new_summary:
                logger.error(
                    f"Iterative type summary (members) failed at chunk {i+1}."
                )
                return None
            running_summary = new_summary

        return running_summary

    def get_hierarchical_summary(
        self, node_data: Dict[str, Any], node_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generic processor for any hierarchical node (File, Directory, etc.).
        Note: :Type nodes are handled by the dedicated get_type_summary method.
        """
        if node_type == "Type":
            logger.warning("get_hierarchical_summary called for a Type node. "
                           "Please use get_type_summary instead.")
            return self.get_type_summary(node_data)

        node_id = node_data["id"]
        db_summary = node_data.get("db_summary")
        dependency_ids = node_data.get("dependency_ids", [])

        is_stale = self.cache_manager.was_dependency_changed(dependency_ids)

        # 1. Check DB state
        if db_summary and not is_stale:
            return {"status": "unchanged", "id": node_id, "summary": db_summary}

        # 2. Check Cache state
        cached_summary = self.cache_manager.get_node_cache(node_id).get(
            "summary"
        )
        if cached_summary and not is_stale:
            return {
                "status": "restored",
                "id": node_id,
                "summary": cached_summary,
            }

        # 3. Regenerate
        child_summaries = [
            self.cache_manager.get_node_cache(dep_id).get("summary")
            for dep_id in dependency_ids
        ]
        child_summaries = [s for s in child_summaries if s]

        if not child_summaries:
            return None  # Cannot generate a parent summary without child context

        # Check if the total context fits into a single prompt
        full_context = " ".join(child_summaries)
        if (
            self.token_manager.get_token_count(full_context)
            < self.token_manager.max_context_token_size
        ):
            context = "; ".join(child_summaries)
            node_name = (
                node_data.get("path")
                or node_data.get("fqn")
                or node_data.get("name")
            )
            prompt = self.prompt_manager.get_hierarchical_summary_prompt(
                node_type, node_name, context
            )
            new_summary = self.llm_client.generate_summary(prompt)
        else:
            node_name = (
                node_data.get("path")
                or node_data.get("fqn")
                or node_data.get("name")
            )
            logger.info(
                f"Context for {node_type} '{node_name}' is too large, "
                "starting iterative summarization..."
            )
            new_summary = self._summarize_hierarchical_iteratively(
                node_data, node_type, child_summaries
            )

        new_summary = self.llm_client.generate_summary(prompt)
        if new_summary:
            return {
                "status": "regenerated",
                "id": node_id,
                "summary": new_summary,
            }

        return None