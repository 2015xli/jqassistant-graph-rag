# Plan: 100 - Project Summary

## 1. Goal

This pass focuses on generating a single, high-level `summary` for the `:Project` node. This summary will provide an overall understanding of the entire codebase, acting as the top-level entry point for an AI agent to grasp the project's purpose and structure.

## 2. Rationale

*   **Top-Level Overview**: The project summary offers a concise description of the entire codebase, useful for initial orientation.
*   **Agent Entry Point**: An AI agent can query the `:Project` node's summary to quickly understand what the project is about before diving into details.
*   **Roll-up Completion**: This pass completes the bottom-up summarization process by aggregating information from the highest-level structural components.

## 3. Actionable Steps (Cypher Queries and LLM Interaction)

This pass will involve:
*   Cypher queries to retrieve summaries of top-level components.
*   LLM calls to generate the project `summary` property.

### Step 3.1: Retrieve Project Context (Summaries of Top-Level Entries)

*   **Logic**: Find the `:Project` node. Gather summaries (`summary` property) from all its direct child `:Entry` nodes (which are top-level directories, summarized in Pass 070).
*   **Cypher (to get project and its contained entry summaries)**:
    ```cypher
    MATCH (p:Project)-[:CONTAINS_ENTRY]->(entry:Entry)
    WHERE entry.summary IS NOT NULL
    RETURN p.name AS projectName, COLLECT(entry.summary) AS entrySummaries
    ```

### Step 3.2: Generate `summary` for the `:Project` Node

*   **Logic**: For the `:Project` node:
    1.  Combine the `entrySummaries` (from Step 3.1).
    2.  Send this combined context to an LLM with a prompt asking for a concise summary of the project's overall purpose, architecture, and key functionalities. Store the result in `p.summary`.
*   **LLM Prompt Example**: "Based on the following summaries of the main entry points and top-level directories of this project, provide a concise summary of the project's overall purpose, architecture, and key functionalities."
*   **Cypher (to update `summary`)**:
    ```cypher
    UNWIND $projects AS projectData
    MATCH (p:Project {name: projectData.projectName})
    SET p.summary = projectData.summary
    ```

## 4. Expected Outcome

*   The single `:Project` node will have a `summary` property.
*   This summary will provide a high-level overview of the entire codebase, derived from the summaries of its top-level components.
