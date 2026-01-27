# Design: NodeSummaryProcessor

## 1. Purpose and Role

The `NodeSummaryProcessor` is the stateless "brain" of the summarization pipeline. It encapsulates the core logic for processing a single graph node to generate a summary or code analysis. Its primary responsibility is to decide *if* a node needs a new summary and *how* to generate it, orchestrating the complex waterfall logic of checking the database, the cache, and finally invoking the LLM. It also handles the critical task of managing LLM context window limits through iterative processing.

## 2. Workflow (The Waterfall Logic)

For any given node, the processor follows a "waterfall" decision process to determine the appropriate action:

1.  **Check for Staleness**: The first step is to determine if the node's summary is "stale." This is done by checking with the `SummaryCacheManager` to see if any of the node's dependencies (e.g., its children in the hierarchy or its member methods) have been regenerated during the current run.
2.  **DB Check (Perfect Hit)**: If the node already has a summary in the database (`db_summary`) and it is *not* stale, the processor returns a status of `"unchanged"`. No further action is needed. For method analysis, this check also involves comparing the hash of the current source code with the stored hash.
3.  **Cache Check (Restorable Hit)**: If the node is stale or has no DB summary, the processor checks the in-memory cache (loaded by `SummaryCacheManager`). If a valid, non-stale summary exists in the cache, it returns a status of `"restored"`. This indicates the summary should be written back to the database.
4.  **Regenerate (LLM Invocation)**: If neither the DB nor the cache can provide a valid summary, the processor proceeds to generate a new one.
    *   **Context Gathering**: It gathers the necessary context for the node, such as the summaries of its children, parents, or its own source code.
    *   **Iterative vs. Single-Shot**: It uses the `TokenManager` to determine if the entire context fits within the LLM's context window.
    *   **Single-Shot**: If the context fits, it formats a single prompt using `PromptManager` and calls the `LlmClient` to generate the summary.
    *   **Iterative**: If the context is too large, it enters an iterative refinement loop. It chunks the context (e.g., lists of child summaries) and repeatedly calls the LLM, feeding it the "summary so far" along with the next chunk of context. This allows it to process arbitrarily large contexts.
    *   **Return Result**: If generation is successful, it returns the new summary with a status of `"regenerated"`.

## 3. Key Methods

-   `__init__(self, llm_client, cache_manager)`: A simple constructor that takes its stateless dependencies.
-   `get_method_code_analysis(...)`: Handles the specific logic for analyzing a method's source code, using content hashing for change detection.
-   `get_method_summary(...)`, `get_type_summary(...)`, `get_hierarchical_summary(...)`: Public methods that serve as entry points for processing different types of nodes. They implement the waterfall logic described above.
-   `_analyze_code_iteratively(...)`, `_summarize_method_context_iteratively(...)`, `_summarize_hierarchical_iteratively(...)`: Private methods that contain the complex logic for iterative refinement when a node's context is too large for a single LLM call.

## 4. Dependencies

The `NodeSummaryProcessor` is stateless and relies on other components to manage state and perform external actions:

-   `llm_client.LlmClient`: To generate summaries via an LLM.
-   `summary_cache_manager.SummaryCacheManager`: To access cached summaries and check the runtime status of dependencies.
-   `prompt_manager.PromptManager`: To get correctly formatted prompt templates.
-   `token_manager.TokenManager`: To count tokens and chunk large contexts.

## 5. Design Rationale

-   **Statelessness**: The `NodeSummaryProcessor` is intentionally designed to be stateless. It does not hold any information about the run in progress. All state is managed externally by the `SummaryCacheManager` (for cache/runtime status) and the `BaseSummarizer` (for the list of items to process). This makes its logic highly predictable, reusable, and easy to test, as its output depends only on its inputs for any given call.
-   **Centralized Intelligence**: It centralizes the most complex part of the system—the decision-making and LLM interaction logic—into a single, focused component. The various `Summarizer` classes are simply drivers that feed data to this processor.
-   **Scalability**: The built-in iterative summarization logic is a key design feature that allows the system to scale to very large and complex codebases without being constrained by the fixed context window of an LLM.
