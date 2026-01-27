# Designing the jQAssistant Graph for GraphRAG

## 1. Introduction

### 1.1. Purpose

This document details the design of the graph processing pipeline that transforms a raw software dependency graph from jQAssistant into a clean, normalized, and enriched structure suitable for a GraphRAG (Retrieval-Augmented Generation) system. It covers the initial, non-AI passes that are a prerequisite for any subsequent summarization or analysis.

The goal of this pipeline is to resolve ambiguities in the raw graph, establish clear and stable identifiers for all entities, and create explicit links between the logical code structure (types, methods) and the physical source files.

### 1.2. Core Technologies

-   **jQAssistant:** Provides the foundational, structural graph of the codebase by scanning compiled artifacts.
-   **Neo4j:** The native graph database used to store and query the software graph.
-   **tree-sitter:** A fast, robust parsing framework used to analyze source code files and extract structural information like type definitions.

## 2. Graph Processing Architecture

The system operates as a multi-stage pipeline that progressively enriches the initial graph. This document focuses on the first stage, which is managed by the `GraphOrchestrator`.

### 2.1. Data Flow

1.  **Scan:** A target software project is scanned by jQAssistant.
2.  **Store:** The raw output is imported into a Neo4j database.
3.  **Enrich:** A series of Python scripts, orchestrated by `GraphOrchestrator`, execute a sequence of "passes" to clean, link, and normalize the graph data.
4.  **Output:** The process results in a "Normalized Graph" which is the required input for the subsequent RAG generation pipeline (summarization and embedding).

### 2.2. Core Components

-   **`GraphOrchestrator`:** Executes the initial passes that normalize, structure, and link the raw jQAssistant data.
-   **`SourceFileLinker`:** A component responsible for parsing all source files and creating the explicit link between a `:Type` node and the `:SourceFile` node that defines it.
-   **`GraphNormalizer`:** A component that runs a series of passes to add canonical properties (`absolute_path`, `entity_id`), labels, and relationships (`:CONTAINS_SOURCE`) to the graph, making it robust and unambiguous.

## 3. The Enrichment Pipeline: A Detailed Pass Design

The enrichment process is broken down into sequential passes, where each pass builds upon the data created by the previous ones. These are all managed by the `GraphOrchestrator`.

---

### **Pass 1: Source File Linking (`SourceFileLinker`)**

-   **Purpose:** To connect abstract code entities (`:Type` nodes) to the physical files (`:File` nodes) where they are defined.
-   **Process:**
    1.  It queries Neo4j to find all `:Artifact:Directory` nodes and the `:File` nodes they `[:CONTAINS]` that represent `.java` or `.kt` source files (excluding `:Directory` nodes).
    2.  For each identified source file, it constructs its absolute path on disk and passes it, along with its relative path in the graph, to language-specific parsers (`JavaSourceParser`, `KotlinSourceParser`).
    3.  The parsers use `tree-sitter` to parse the file content and extract the package name and Fully Qualified Names (FQNs) of all top-level types declared within it.
    4.  Finally, it executes a Cypher query to find the `:Type` node for each FQN and the `:File` node for the corresponding file path, then creates a `[:WITH_SOURCE]` relationship from the `:Type` node to its containing `:File` node.
-   **Output:** A graph where `:Type` nodes are directly linked to the `:File` nodes that contain their source code.

---

### **Pass 2: Graph Normalization (`GraphNormalizer`)**

The `GraphNormalizer` executes several sub-passes in sequence:

#### **2a. Create Project Root**

-   **Purpose:** To create a single root `:Project` node for the entire analysis.
-   **Process:** Merges a single `:Project` node into the graph, using the project directory's name and absolute path.

#### **2b. Normalize Paths**

-   **Purpose:** To standardize all file paths with a canonical `absolute_path` property.
-   **Process:**
    1.  Identifies directory-based `:Artifact` nodes and labels them as `:Entry` points.
    2.  For all `:File` and `:Directory` nodes contained within an `:Entry` node, it constructs an `absolute_path` by concatenating the entry's absolute path with the node's own relative `fileName`.
-   **Output:** A graph with consistent, absolute paths on all file-system-related nodes, resolving the ambiguity of jQAssistant's `fileName` property.

#### **2c. Identify and Label Source Files**

-   **Purpose:** To explicitly label files that contain source code.
-   **Process:** Finds all `:File` nodes whose `absolute_path` ends with `.java` or `.kt` and adds a `:SourceFile` label to them.
-   **Output:** `:File` nodes for source code are now also labeled as `:SourceFile`.

#### **2d. Identify Entities and Create Stable IDs**

-   **Purpose:** To assign a stable, unique, and deterministic identifier to every node that will be part of the RAG process. This ID is essential for caching and dependency tracking.
-   **Process:**
    1.  Ensures a database uniqueness constraint exists for `(:Entity {entity_id})`.
    2.  Adds the `:Entity` label to all relevant nodes (`:Project`, `:Artifact`, `:File`, `:Type`, `:Member`, etc.).
    3.  Generates an `entity_id` for each `:Entity` node. This ID is an MD5 hash of a composite key that guarantees uniqueness. For example, for a `:Type` node, the key is `"{Artifact.fileName} + {Node.fileName}"`.
-   **Output:** All relevant nodes are labeled `:Entity` and have a unique, stable `entity_id` property.

#### **2e. Establish Direct Source Hierarchy**

-   **Purpose:** To create a clean, traversable file-system hierarchy for the source code.
-   **Process:** Creates `[:CONTAINS_SOURCE]` relationships to form a tree from the `:Project` node down through `:Directory` nodes to other `:Directory` and `:SourceFile` nodes. This pass now processes directories level by level, from the deepest to the shallowest. For each level, it first links directories to their direct `:SourceFile` children and then links directories to their direct `:Directory` children. This level-by-level approach ensures that all child relationships are established before a parent attempts to link to them, preventing inconsistencies and providing a robust tree structure for hierarchical summarization.
-   **Output:** A browsable source code hierarchy using a single, clear relationship type.

#### **2f. Link Members to Source Files**

-   **Purpose:** To extend the source linking from types down to their members (`:Method` and `:Field`).
-   **Process:** For each `:Method` and `:Field`, it traverses to its parent `:Type`, finds the `:SourceFile` linked to that type (via the relationship created in Pass 1), and creates a direct `[:WITH_SOURCE]` relationship from the member to that same file.
-   **Output:** `:Method` and `:Field` nodes are now directly linked to the file containing their source code, enabling easy code extraction for analysis.

## 4. Final Output

The output of this entire pipeline is a **Normalized Graph**. This graph has a clear structure, unambiguous paths, stable identifiers, and direct links between the logical and physical code structures. It is the required input for the next stage of the system: the RAG generation pipeline, which is responsible for summarization and embedding.
