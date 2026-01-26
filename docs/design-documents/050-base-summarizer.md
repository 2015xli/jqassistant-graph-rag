# Design: BaseSummarizer

## 1. Purpose and Role

The `BaseSummarizer` is an abstract base class that provides a reusable, parallelized workflow for all specific summarization passes (e.g., `MethodSummarizer`, `TypeSummarizer`, `DirectorySummarizer`). It implements the **Template Method design pattern** to define the skeleton of a summarization pass, allowing concrete subclasses to override specific steps (like the queries to run or the processing logic to invoke) while inheriting the shared machinery for execution, parallelization, and database updates.

## 2. Workflow (The Template Method)

The core of the `BaseSummarizer` is the `process_batch` method, which orchestrates the processing of a list of items fetched from the graph.

1.  **Item Processing**: The `process_batch` method iterates through the list of items to be processed. For each item, it submits a task to a `ThreadPoolExecutor`.
2.  **Parallel Execution**: The thread pool executes the `_process_and_handle_item` method for each item in parallel. This method represents the "template method" itself.
3.  **The Template (`_process_and_handle_item`)**: This method defines the fixed sequence of operations for a single item:
    a. **Preparation (Optional Hook)**: It first calls `_prepare_item()`, an optional hook that subclasses can implement to modify or enrich the item before processing (e.g., reading a method's source code from a file).
    b. **Core Processing (Abstract)**: It then calls `_get_processor_result()`, an **abstract method** that every concrete subclass *must* implement. This is the primary variation point, where each summarizer specifies which method on the `NodeSummaryProcessor` to call (e.g., `get_type_summary` or `get_method_analysis`).
    c. **Result Handling**: Finally, it passes the result from the processor to `_handle_result()`. This method checks the status (`"regenerated"`, `"restored"`, `"unchanged"`) and updates the `SummaryCacheManager` accordingly. It only returns data if a database update is required.
4.  **Batch Update**: After all parallel tasks are complete, the `process_batch` method collects all the results that require a database update. It then calls `_get_update_query()` (another **abstract method** that subclasses must implement) to get the appropriate Cypher query and executes a single, efficient batch-write operation to Neo4j.

## 3. Key Methods

-   `run()`: An **abstract method** that subclasses must implement. This is the main entry point for a pass, responsible for fetching the initial list of items from the graph and starting the `process_batch` workflow.
-   `process_batch(...)`: The main driver method that manages the parallel execution of a list of items and the final database update.
-   `_process_and_handle_item(...)`: The core "template method" that defines the fixed algorithm for processing a single item.
-   `_get_processor_result(...)`: An **abstract method** for subclasses to define their specific processing logic by calling the appropriate `NodeSummaryProcessor` method.
-   `_get_update_query()`: An **abstract method** for subclasses to provide the specific Cypher query needed to persist their results to the graph.
-   `_prepare_item(...)`: An optional "hook" method that subclasses can override for pre-processing tasks.

## 4. Dependencies

-   `neo4j_manager.Neo4jManager`: To execute read and write queries.
-   `node_summary_processor.NodeSummaryProcessor`: To perform the actual summarization logic for an item.

## 5. Design Rationale

-   **Don't Repeat Yourself (DRY)**: The primary reason for this component is to avoid duplicating the complex logic for parallel processing, progress bar display (`tqdm`), result handling, cache interaction, and batch database writes. All this machinery is implemented once in the base class.
-   **Extensibility and Consistency**: The Template Method pattern provides a clear and consistent structure for all summarization passes. To add a new pass, a developer only needs to subclass `BaseSummarizer` and implement the three abstract methods (`run`, `_get_processor_result`, `_get_update_query`). This makes the system easy to extend while ensuring all passes behave consistently.
-   **Performance**: By using a `ThreadPoolExecutor`, the `BaseSummarizer` can significantly speed up the summarization process by parallelizing the most expensive operations (LLM calls and file I/O). The single batch-write at the end is also much more efficient than updating the database one node at a time.
