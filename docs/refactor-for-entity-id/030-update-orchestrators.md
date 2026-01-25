# 030: Update Orchestrators

This document details the plan to update the `GraphOrchestrator` to incorporate the new entity identification pass into the main enrichment workflow.

## 1. `GraphOrchestrator` Modification

The `run_enrichment_passes` method in the `GraphOrchestrator` defines the sequence of operations. A new step will be added to this sequence.

### 1.1. New Pass Execution

A call to the new `graph_normalizer.identify_entities()` method will be added.

*   **Placement**: This pass must run *after* all initial graph structuring and property-setting passes are complete, but *before* any summarization passes begin. The ideal placement is at the end of the `run_enrichment_passes` method, as this method is always executed before the `RagOrchestrator` begins its work.

*   **Updated Sequence in `run_enrichment_passes`**:
    1.  `_run_source_file_linker()`
    2.  `_run_normalize_paths_and_project_root()`
    3.  `_run_identify_and_label_source_files()`
    4.  `_run_establish_direct_source_hierarchy()`
    5.  `_run_link_members_to_source_files()`
    6.  **`_run_identify_entities()` (New)**

### 1.2. New Private Method

A new private method, `_run_identify_entities()`, will be created within the `GraphOrchestrator` to encapsulate the call to the normalizer, consistent with the existing pattern.

```python
def _run_identify_entities(self):
    """Executes the Entity Identification pass."""
    logger.info("\n>>> Running Entity Identification")
    try:
        normalizer = GraphNormalizer(self.neo4j_manager)
        normalizer.identify_entities()
        logger.info(">>> Pass Complete")
    except Exception as e:
        logger.error(f"Entity Identification pass failed: {e}", exc_info=True)
        raise
```

## 2. `RagOrchestrator`

No changes are required in the `RagOrchestrator`. Because the `entity_id`s will have been created by the time the `GraphOrchestrator` completes its work, the `RagOrchestrator` and its summarizers will be able to rely on them being present in the graph.

This final change ensures that the `entity_id` generation is a standard, automatic part of the graph preparation process.

```