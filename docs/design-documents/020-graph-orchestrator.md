# Design: GraphOrchestrator

## 1. Purpose and Role

The `GraphOrchestrator` is the central coordinator for the entire graph normalization and enrichment process. Its sole responsibility is to execute a series of pre-defined passes in a specific, logical order to transform the raw jQAssistant graph into a clean, stable, and analyzable state.

It acts as a high-level "director," instantiating the necessary specialized handler classes and invoking their methods (passes) in the correct sequence. This decouples the high-level workflow from the low-level implementation of each pass.

## 2. Workflow

The orchestrator follows a strict, four-phase workflow:

1.  **Initialization**: Upon creation, it receives an active `Neo4jManager` instance which it passes to the handlers.
2.  **Phase 1: Basic Normalization**: It invokes the `GraphBasicNormalizer` to add canonical `absolute_path` properties to all filesystem nodes and to label source code files as `:SourceFile`.
3.  **Phase 2: Source Code Integration**: It calls the `SourceFileLinker` to parse the identified source files and create `[:WITH_SOURCE]` relationships between `:Type`/`:Member` nodes and their corresponding `:SourceFile` nodes.
4.  **Phase 3: Hierarchical Structure**: It uses the `GraphTreeBuilder` to determine the project root, create a single `:Project` node, and build a clean `[:CONTAINS_SOURCE]` hierarchical overlay.
5.  **Phase 4: Entity Identification**: Finally, it calls the `GraphEntitySetter` to apply the `:Entity` label to all relevant nodes and generate a stable, unique `entity_id` for each.

## 3. Key Methods

-   `__init__(self, neo4j_manager: Neo4jManager)`: The constructor requires an active `Neo4jManager`.
-   `run_enrichment_passes()`: This is the main public method. It orchestrates the instantiation and execution of the specialized handlers in the correct order.

## 4. Dependencies

The `GraphOrchestrator` depends on the following components:

-   `neo4j_manager.Neo4jManager`: To pass to the handlers.
-   `graph_basic_normalizer.GraphBasicNormalizer`: For Phase 1 passes.
-   `source_file_linker.SourceFileLinker`: For Phase 2 passes.
-   `graph_tree_builder.GraphTreeBuilder`: For Phase 3 passes.
-   `graph_entity_setter.GraphEntitySetter`: For Phase 4 passes.

## 5. Design Rationale

The `GraphOrchestrator` is designed as a pure "director" or "facade." This design offers several advantages:

-   **Separation of Concerns**: It cleanly separates the *what* and *when* of the process (the orchestration logic) from the *how* (the implementation of each pass).
-   **Centralized Control**: It provides a single, clear entry point for the entire graph preparation workflow, making it easy to understand and manage.
-   **Modularity and Reconfigurability**: The order of passes can be easily changed within the orchestrator without modifying any of the handler classes. New passes can be added with minimal friction.