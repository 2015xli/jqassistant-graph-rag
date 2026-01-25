import logging
from neo4j_manager import Neo4jManager
from method_analyzer import MethodAnalyzer
from method_summarizer import MethodSummarizer
from type_summarizer import TypeSummarizer
from source_file_summarizer import SourceFileSummarizer
from directory_summarizer import DirectorySummarizer
from package_summarizer import PackageSummarizer
from project_summarizer import ProjectSummarizer
from entity_embedder import EntityEmbedder
from llm_client import get_llm_client, get_embedding_client, LlmClient, EmbeddingClient
from summary_cache_manager import SummaryCacheManager
from node_summary_processor import NodeSummaryProcessor
from pathlib import Path

logger = logging.getLogger(__name__)

class RagOrchestrator:
    """
    Manages and executes the sequence of RAG (summary and embedding) generation passes.
    """
    def __init__(self, neo4j_manager: Neo4jManager, project_path: Path, llm_api: str):
        self.neo4j_manager = neo4j_manager
        self.project_path = project_path
        self.project_name = self.project_path.name
        self.llm_api = llm_api

        # Initialize core components
        self.llm_client: LlmClient = get_llm_client(self.llm_api)
        self.embedding_client: EmbeddingClient = get_embedding_client("sentence-transformer")
        self.cache_manager = SummaryCacheManager(str(self.project_path))
        self.node_summary_processor = NodeSummaryProcessor(self.llm_client, self.cache_manager)

        # Initialize all pass handlers with the necessary components
        self.method_analyzer = MethodAnalyzer(neo4j_manager, self.node_summary_processor)
        self.method_summarizer = MethodSummarizer(neo4j_manager, self.node_summary_processor)
        self.type_summarizer = TypeSummarizer(neo4j_manager, self.node_summary_processor)
        self.source_file_summarizer = SourceFileSummarizer(neo4j_manager, self.node_summary_processor)
        self.directory_summarizer = DirectorySummarizer(neo4j_manager, self.node_summary_processor)
        #TODO: how to use the summary of package? how to determine the boundary of package directory?
        self.package_summarizer = PackageSummarizer(neo4j_manager, self.node_summary_processor)
        self.project_summarizer = ProjectSummarizer(neo4j_manager, self.node_summary_processor)
        self.entity_embedder = EntityEmbedder(neo4j_manager, self.embedding_client)

        logger.info(f"Initialized RagOrchestrator for project: {self.project_name} with LLM API: {self.llm_api}")

    def run_rag_passes(self):
        """
        Executes the full sequence of RAG generation passes with caching.
        """
        self.cache_manager.load()
        try:
            logger.info(f"--- Starting All RAG Generation Passes for project: {self.project_name} ---")

            # The sequence of passes remains the same
            self.method_analyzer.run()
            self.method_summarizer.run()
            self.type_summarizer.run()
            self.source_file_summarizer.run()
            self.directory_summarizer.run()
            #TODO: how to use the summary of package? how to determine the boundary of package directory?
            #self.package_summarizer.run()
            self.project_summarizer.run()
            self.entity_embedder.add_entity_labels_and_embeddings()

            logger.info(f"--- All RAG Generation Passes for project: {self.project_name} Complete ---")
        finally:
            # Ensure the cache is saved even if an error occurs
            self.cache_manager.save()
