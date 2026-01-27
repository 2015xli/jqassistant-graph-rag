# Design: SummaryCacheManager

## 1. Purpose and Role

The `SummaryCacheManager` is a critical stateful component responsible for the persistence, integrity, and in-memory management of the summary cache. Its primary role is to make the expensive RAG generation process efficient and stateful between runs. It achieves this by saving all generated summaries and content hashes to disk, allowing subsequent runs to avoid re-processing unchanged parts of the codebase.

Furthermore, it plays a vital role in dependency tracking during a run by maintaining a `runtime_status` of which nodes have been changed, enabling the system to correctly determine if a node's summary has become "stale."

## 2. Workflow and Key Logic

### a. Cache Persistence (Load/Save)

1.  **Loading (`load`)**: When the `RagOrchestrator` starts, it calls `load()`. The manager attempts to read the `summary_cache.json` file from the `.cache` directory and deserialize its content into the in-memory `self.cache` dictionary. If the file doesn't exist or is corrupt, it starts with an empty cache.
2.  **Saving (`save`)**: After the RAG process finishes (or fails), `save()` is called. This triggers a safe, multi-stage save process to prevent data corruption:
    *   **Write to Temp**: The entire in-memory cache is written to a temporary file (`summary_cache.json.tmp`).
    *   **Sanity Check**: Before overwriting the main cache, a sanity check is performed. If the new cache is drastically smaller than the old one, the promotion is aborted to prevent accidental data loss (e.g., due to a bug causing an empty cache).
    *   **Backup Rotation**: The existing cache files are rotated: `.json` becomes `.bak.1`, and `.bak.1` becomes `.bak.2`. This maintains two previous versions as a fallback.
    *   **Promotion**: The temporary file is moved to become the new `summary_cache.json`.

### b. In-Memory Operations

1.  **Cache Access (`get_node_cache`, `update_node_cache`)**: Provides simple dictionary-like access to the in-memory cache for a given `node_id`. The `NodeSummaryProcessor` uses this to retrieve cached summaries and hashes.
2.  **Runtime Status (`set_runtime_status`)**: During a run, when the `NodeSummaryProcessor` successfully regenerates a summary for a node, it calls `set_runtime_status(node_id, 'regenerated')`. This flags the node as "changed" within the current run in the `self.runtime_status` dictionary.
3.  **Dependency Checking (`was_dependency_changed`)**: This is a key method used by the `NodeSummaryProcessor`. Given a list of dependency `node_id`s, it checks the `runtime_status` dictionary to see if any of them have been flagged as "changed" during the current run. This is how the system determines if a parent node's summary is "stale" and needs to be re-evaluated.

## 3. Key Methods and Properties

-   `cache_dir`, `cache_file`, `tmp_cache_file`, `bak1_file`, `bak2_file`: Path objects defining the cache file locations.
-   `cache`: The primary in-memory dictionary holding all cached data (`{node_id: {summary: "...", code_hash: "..."}}`).
-   `runtime_status`: A dictionary holding the state of the *current run only* (`{node_id: {changed: True}}`). It is not persisted.
-   `load()`: Loads the cache from disk.
-   `save()`: Saves the cache to disk using the safe promotion process.
-   `get_node_cache(node_id)`: Retrieves cache data for a single node.
-   `update_node_cache(node_id, data)`: Updates the in-memory cache for a node.
-   `was_dependency_changed(dependency_ids)`: Checks if any of the given dependencies have been regenerated in the current run.

## 4. Dependencies

The `SummaryCacheManager` is a self-contained utility and has no dependencies on other project components, though many components depend on it.

## 5. Design Rationale

-   **Efficiency**: The primary motivation is performance. LLM calls are slow and expensive. By caching their results, the system can avoid regenerating summaries for the vast majority of the codebase that hasn't changed between runs, leading to massive performance gains.
-   **Robustness**: The safe-save mechanism (temp file, sanity check, and backup rotation) is a critical design feature to protect against data loss. An incomplete or corrupted cache file could force a full, expensive regeneration of the entire project.
-   **Decoupling State**: The manager decouples the state of the RAG process from the core logic. The `NodeSummaryProcessor` remains stateless because the `SummaryCacheManager` is responsible for both long-term persistence (the JSON file) and short-term, run-specific state (the `runtime_status` dictionary). This separation makes the overall architecture cleaner and easier to reason about.
-   **Correctness**: The `runtime_status` and `was_dependency_changed` logic is fundamental to the correctness of the hierarchical summarization. It ensures that changes propagate up the hierarchy correctly—if a method changes, its class summary is re-evaluated, then its file summary, and so on.
