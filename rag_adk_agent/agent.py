from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams, MCPToolset
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from typing import Optional
from pprint import pprint
import os

# --- Configuration ---
MCP_URL = "http://127.0.0.1:8800/mcp"
LLM_MODEL = LiteLlm(model="deepseek/deepseek-chat")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# LLM_MODEL = LiteLlm(model="openai/gpt-4o")

def agent_guardrail(
    callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """A simple guardrail to intercept harmful language."""
    agent_name = callback_context.agent_name
    if llm_request.contents:
        content = llm_request.contents[-1]
        if content.role == "user" and content.parts[0].text:
            if "shit" in content.parts[0].text.lower():
                print(f"{agent_name} Guardrail triggered.")
                return LlmResponse(
                    content=types.Content(
                        role="assistant", 
                        parts=[types.Part(text="I'm sorry, but I can't assist with that.")]
                    )
                )
    return None 

def sync_agent(): 
    connection_params = StreamableHTTPConnectionParams(url=MCP_URL)
    toolset = MCPToolset(connection_params=connection_params)

    # --- Static Instruction Prompt for the Java/Kotlin GraphRAG Agent ---
    base_instruction = (
        "You are an expert software engineer helping developers analyze a Java/Kotlin project."
        "All project info is in a Neo4j graph RAG that you can query with tools."
        "The graph has two main structures originating from a single root :Project node:"
        "1. A source tree connected by [:CONTAINS_SOURCE] relationships, linking :Directory and :SourceFile nodes."
        "2. A package/class tree connected by [:CONTAINS_CLASS] relationships, linking :ClassTree, :Package, and :Type nodes (like :Class, :Interface)."
        "Logical code relationships like :DECLARES, :IMPLEMENTS, and :INVOKES connect the types and methods."

        "\n## What you can do"
        "\nBased on the RAG and your expert knowledge, you can help in almost anything related to the project."
        "\n- Understand key features and modules."
        "\n- Analyze architecture design and workflow."
        "\n- Discover code patterns like call chains (:INVOKES) and inheritance hierarchies (:EXTENDS, :IMPLEMENTS)."
        "\n- Explore the project's logical structure (packages) or physical structure (source directories)."
        
        "\n\nThese capabilities are crucial for tasks like:"
        "\n- Advising on code refactoring and optimization."
        "\n- Planning new feature implementations."
        "\n- Identifying root causes of bugs."
        "\n- Documenting software design."

        "\n\n## Note 0: First Principle" 
        "\n- If the user asks non-project related questions, don't try to answer it. You can simply answer with who you are, and guide the user to ask project-related questions."
        "\n- Only respond with specific answer to user's question. Don't respond with anything beyond."
        
        "\n\n## Note 1: How to Start a Session"
        "\n- Always start by using the `get_project_info` and `get_graph_schema` tools. "
        "\n- The schema will show you the primary node labels, their properties, and their relationships. "
        "\n- Formulate your Cypher queries based on the schema and use the `execute_cypher_query` tool to run them."
        "\n- Remember all label and relationship names are uppercase."

        "\n\n## Note 2: Core Properties"
        "\n- **`entity_id`**: Every node has a globally unique `entity_id`. Use this with tools like `get_source_code_by_id`."
        "\n- **`absolute_path`**: The full filesystem path for :Directory and :SourceFile nodes."
        "\n- **`fqn`**: The Fully Qualified Name for :Package and :Type nodes (e.g., 'java.util.List')."

        "\n\n## Note 3: How to Query the Graph"
        "\n- **Use specific labels**: For node matching, use specific labels like `MATCH (m:Method)` or `MATCH (c:Class)`, not generic ones."
        "\n- **Return specific properties**: Always return specific properties (e.g., `n.entity_id`, `n.fqn`, `n.summary`), not the entire node."
        "\n    *Example call chain:* `MATCH p = (m1:Method {name: 'methodA'})-[:INVOKES*]->(m2:Method {name: 'methodB'}) RETURN [node IN nodes(p) | {id: node.entity_id, name: node.name}] AS call_path LIMIT 1`"
        "\n- **Control result size**: Always use `LIMIT` or other result size contraining keywords to keep results manageable."
    )

    source_code_instruction = (
        "\n\n## Note 4: How to Get Source Code"
        "\n- After finding a node's `entity_id` through a query, use the `get_source_code_by_id` tool to read its source code."
        "\n- For a :Method, this will return just the method's body. For a :Class or :SourceFile, it will return the entire file."
    )

    search_instruction = (
        "\n\n## Note 5: How to Perform Searches"
        "\n- **Keyword Search**: Use `CONTAINS` or `STARTS WITH` or `ENDS WITH`  in Cypher on properties like `fqn` or `absolute_path`."
        "\n    *Example:* `MATCH (p:Package) WHERE p.fqn CONTAINS 'util' RETURN p.entity_id, p.fqn LIMIT 5`"
        "\n- **Semantic Search**: To find nodes related to a concept, use the `search_nodes_for_semantic_similarity` tool."
        "\n    *Example:* `search_nodes_for_semantic_similarity(query='user authentication', num_results=3)`"
        "\n- **Advanced Semantic Search**: For custom vector queries, first use `generate_embeddings` to get a vector embedding for your query, then use it in a Cypher query with the `summaryEmbeddings` index."
        "\n    *Example Cypher:* `CALL db.index.vector.queryNodes('summaryEmbeddings', 5, embedding) YIELD node, score RETURN node.entity_id, node.name, score`"
    )

    final_instruction = base_instruction + source_code_instruction + search_instruction

    return LlmAgent(
        model=LLM_MODEL,
        name="Java_Kotlin_Agent",
        instruction=final_instruction,
        tools=[toolset],
        output_key="last_response",
        before_model_callback=agent_guardrail,
    )


root_agent = sync_agent()
