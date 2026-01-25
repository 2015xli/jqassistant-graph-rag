# 020: Refactor Summarizers to Use entity_id

This document details the plan to refactor all summarizer classes to exclusively use the new `entity_id` property for all identification, dependency tracking, and update operations. This change is crucial for making the caching mechanism stable and reliable.

This refactoring will touch every summarizer class. The changes are consistent across all of them.

## 1. `MethodAnalyzer`

*   **Main Query (`run` method)**: The query will be updated to return `m.entity_id AS id` instead of `elementId(m)`.
*   **Update Query (`_get_update_query`)**: The `MATCH` clause will be changed to `MATCH (m:Method {entity_id: item.id})`.

## 2. `MethodSummarizer`

*   **Main Query (`run` method)**:
    *   The query will return `m.entity_id AS id`.
    *   The collection of `callers` and `callees` will be updated to collect `caller.entity_id` and `callee.entity_id`.
*   **Update Query (`_get_update_query`)**: The `MATCH` clause will be changed to `MATCH (m:Method {entity_id: item.id})`.

## 3. `TypeSummarizer`

*   **Hierarchy Query (`_get_types_by_inheritance_level`)**: The queries that determine the inheritance levels will be updated to return and process `t.entity_id`.
*   **Context Query (`_get_context_for_ids`)**:
    *   The query will match on `elementId(t) IN $ids` (since the level-building returns elementIds for performance) but will `RETURN t.entity_id AS id`.
    *   The collection of `parent_ids` and `member_ids` will be updated to collect `p.entity_id` and `m.entity_id`.
*   **Update Query (`_get_update_query`)**: The `MATCH` clause will be changed to `MATCH (t:Type {entity_id: item.id})`.

## 4. `SourceFileSummarizer`

*   **Main Query (`run` method)**:
    *   The query will return `sf.entity_id AS id`.
    *   The collection of `dependency_ids` will be updated to collect `t.entity_id`.
*   **Update Query (`_get_update_query`)**: The `MATCH` clause will be changed to `MATCH (sf:SourceFile {entity_id: item.id})`.

## 5. `DirectorySummarizer`

*   **Main Query (`_get_directories_ordered_by_depth`)**:
    *   The query will return `d.entity_id AS id`.
    *   The collection of `dependency_ids` will be updated to collect `child.entity_id`.
*   **Update Query (`_get_update_query`)**: The `MATCH` clause will be changed to `MATCH (d:Directory {entity_id: item.id})`.

## 6. `PackageSummarizer`

*   **Main Query (`_get_packages_ordered_by_depth`)**:
    *   The query will return `p.entity_id AS id`.
    *   The collection of `dependency_ids` will be updated to collect `child.entity_id`.
*   **Update Query (`_get_update_query`)**: The `MATCH` clause will be changed to `MATCH (p:Package {entity_id: item.id})`.

## 7. `ProjectSummarizer`

*   **Main Query (`_get_project_with_context`)**:
    *   The query will return `p.entity_id AS id`.
    *   The collection of `dependency_ids` will be updated to collect `child.entity_id`.
*   **Update Query (`_get_update_query`)**: The `MATCH` clause will be changed to `MATCH (p:Project {entity_id: item.id})`.

By systematically applying these changes, we will completely remove the dependency on the unstable `elementId` and transition the entire summarization pipeline to the new, stable `entity_id`.
