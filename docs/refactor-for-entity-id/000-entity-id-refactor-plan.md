# 000: High-Level Plan for entity_id Refactoring

This document outlines the high-level plan to refactor the graph enrichment and summarization engine to use a stable, synthetic `entity_id` for all relevant nodes. This change is critical to fix a major flaw in the caching mechanism, which currently relies on the unstable `elementId`.

## The Problem

The current caching system uses Neo4j's internal `elementId` as the key for storing and retrieving summaries. This ID is not guaranteed to be stable across different database runs or instances, which completely invalidates the purpose of a persistent cache. Furthermore, simple properties like `fqn` are not guaranteed to be unique across different artifacts (e.g., two JARs containing the same class).

## The Solution

We will introduce a new, guaranteed unique, and stable property called `entity_id` for all nodes involved in the summarization process. This ID will be a hash generated from a composite key that uniquely identifies the node within the project's scope.

## The Plan

The refactoring will be executed in three main phases:

1.  **Phase 1: Introduce the Entity Identification Pass**: A new normalization pass will be created. Its sole responsibility will be to generate the `entity_id` for all relevant nodes and apply a common `:Entity` label.
    *   *Detailed Plan*: `010-implement-entity-identification-pass.md`

2.  **Phase 2: Globally Refactor Summarizers**: Every summarizer component will be updated to stop using `elementId` and exclusively use the new `entity_id` for identifying nodes, fetching dependencies, and updating summaries.
    *   *Detailed Plan*: `020-refactor-summarizers-to-use-entity-id.md`

3.  **Phase 3: Update Orchestrators**: The `GraphOrchestrator` will be updated to execute the new entity identification pass at the correct point in the enrichment sequence.
    *   *Detailed Plan*: `030-update-orchestrators.md`

This refactoring will result in a robust, reliable, and architecturally sound caching and identification system.
