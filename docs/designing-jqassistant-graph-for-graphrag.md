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

-   **`GraphOrchestrator`:** The central coordinator that executes the entire sequence of enrichment passes in a defined order.
-   **`GraphBasicNormalizer`:** The first handler, responsible for adding canonical `absolute_path` properties and labeling `:SourceFile` nodes.
-   **`SourceFileLinker`:** The second handler, responsible for parsing source files (identified by the normalizer) and creating `[:WITH_SOURCE]` links from types and members to their source files.
-   **`GraphTreeBuilder`:** The third handler, which creates the root `:Project` node and builds the clean `[:CONTAINS_SOURCE]` source code hierarchy.
-   **`ArtifactDataNormalizer`:** A critical handler that fundamentally corrects the graph structure by relocating misplaced `:Artifact` labels, rewriting the core `[:CONTAINS]` relationships, and then building the clean `[:CONTAINS_CLASS]` hierarchy overlay.
-   **`GraphEntitySetter`:** The final handler, responsible for applying the `:Entity` label and generating the stable `entity_id` for all relevant nodes.

## 3. The Enrichment Pipeline: A Detailed Pass Design

The enrichment process is broken down into five sequential phases, where each phase builds upon the data created by the previous ones. These are all managed by the `GraphOrchestrator`.

---

### **Phase 1: Basic Normalization (`GraphBasicNormalizer`)**

This phase lays the essential groundwork for all other passes.

#### **1a. Add Absolute Paths**

-   **Purpose:** To standardize all file paths with a canonical `absolute_path` property.
-   **Process:**
    1.  Sets the `absolute_path` on `:Artifact:Directory` nodes to equal their `fileName`.
    2.  For all `:File` and `:Directory` nodes contained within an artifact, it constructs an `absolute_path` by concatenating the artifact's absolute path with the node's own relative `fileName`.
-   **Output:** A graph with consistent, absolute paths on all file-system-related nodes, resolving the ambiguity of jQAssistant's `fileName` property.

#### **1b. Label Source Files**

-   **Purpose:** To explicitly label files that contain source code.
-   **Process:** Finds all `:File` nodes whose `absolute_path` ends with `.java` or `.kt` and adds a `:SourceFile` label to them.
-   **Output:** `:File` nodes for source code are now also labeled as `:SourceFile`, making them easy to query.

---

### **Phase 2: Source Code Integration (`SourceFileLinker`)**

With paths and source files clearly identified, this phase connects the logical graph to the physical source code.

#### **2a. Link Types to Source Files**

-   **Purpose:** To connect abstract code entities (`:Type` nodes) to the physical files (`:SourceFile` nodes) where they are defined.
-   **Process:**
    1.  It queries Neo4j to find all nodes with the `:SourceFile` label.
    2.  It passes the `absolute_path` of each `:SourceFile` to language-specific parsers (`JavaSourceParser`, `KotlinSourceParser`).
    3.  The parsers use `tree-sitter` to extract the Fully Qualified Names (FQNs) of all top-level types declared within each file.
    4.  Finally, it executes a Cypher query to create a `[:WITH_SOURCE]` relationship from each `:Type` node (matched by FQN) to its containing `:SourceFile` node (matched by `absolute_path`).
-   **Output:** A graph where `:Type` nodes are directly linked to the `:SourceFile` nodes that contain their source code.

#### **2b. Link Members to Source Files**

-   **Purpose:** To extend the source linking from types down to their members (`:Method` and `:Field`).
-   **Process:** For each `:Method` and `:Field`, it traverses to its parent `:Type`, finds the `:SourceFile` linked to that type, and creates a direct `[:WITH_SOURCE]` relationship from the member to that same file.
-   **Output:** `:Method` and `:Field` nodes are now directly linked to the file containing their source code, enabling easy code extraction for analysis.

---

### **Phase 3: Hierarchical Structure (`GraphTreeBuilder`)**

This phase builds a clean, traversable hierarchy for the project's source code.

#### **3a. Create Project Root**

-   **Purpose:** To create a single root `:Project` node for the entire analysis.
-   **Process:** Auto-detects the project root from `:Artifact:Directory` nodes, merges a single `:Project` node into the graph, and links all `:Artifact` nodes to it.

#### **3b. Establish Direct Source Hierarchy**

-   **Purpose:** To create a clean, traversable file-system hierarchy for the source code.
-   **Process:** Creates `[:CONTAINS_SOURCE]` relationships to form a tree from the `:Project` node down through `:Directory` nodes to other `:Directory` and `:SourceFile` nodes. This is done level-by-level from the bottom up to ensure correctness.
-   **Output:** A browsable source code hierarchy using a single, clear relationship type.

---

### **Phase 4: Package Data Normalization (`PackageDataNormalizer`)**

This new phase builds a second, parallel hierarchy for the project's compiled class and package structure.

#### **4a. Identify and Validate Package Trees**

-   **Purpose:** To find reliable package structures within the graph, correcting the often-ambiguous `fqn` property on directories.
-   **Process:**
    1.  First, it labels all `:Jar:Artifact` nodes as `:ClassTree`, as they are a reliable source of package structure.
    2.  Then, for each `:Directory:Artifact`, it uses a heuristic to find potential package structures. It finds a deeply nested `:Class` file, uses its correct `fqn` to infer the package path, and validates this path by walking up the directory tree.
    3.  If a structure is validated, its root directory is also labeled `:ClassTree`, and the `fqn` properties of all its sub-directories are corrected.
-   **Output:** A set of `:ClassTree` nodes that act as the roots of valid package hierarchies.

#### **4b. Establish Direct Class Hierarchy**

-   **Purpose:** To create a clean, traversable hierarchy for the package and class structure.
-   **Process:** This pass iterates through each identified `:ClassTree` root. Within each tree, it uses a bottom-up, level-by-level approach to create `[:CONTAINS_CLASS]` relationships. Crucially, it uses the existing `[:CONTAINS]` relationship as a guardrail to ensure that links are only created between nodes that belong to the same artifact, preventing incorrect relationships between different JARs that share common package paths (e.g., `org.apache`).
-   **Output:** A second, browsable hierarchy parallel to the source tree, representing the project's compiled and dependency structure.

---

### **Phase 5: Entity Identification (`GraphEntitySetter`)**

This is the final normalization pass before summarization can begin.

#### **5a. Identify Entities and Create Stable IDs**

-   **Purpose:** To assign a stable, unique, and deterministic identifier to every node that will be part of the RAG process. This ID is essential for caching and dependency tracking.
-   **Process:**
    1.  Ensures a database uniqueness constraint exists for `(:Entity {entity_id})`.
    2.  Adds the `:Entity` label to all relevant nodes (`:Project`, `:Artifact`, `:File`, `:Type`, `:Member`, etc.).
    3.  Generates an `entity_id` for each `:Entity` node. This ID is an MD5 hash of a composite key that guarantees uniqueness (e.g., `"{Artifact.fileName} + {Node.fileName}"`).
-   **Output:** All relevant nodes are labeled `:Entity` and have a unique, stable `entity_id` property.

## 4. Final Output

The output of this entire pipeline is a **Normalized Graph**. This graph has a clear structure with two parallel hierarchies (`[:CONTAINS_SOURCE]` and `[:CONTAINS_CLASS]`), unambiguous paths, stable identifiers, and direct links between the logical and physical code structures. It is the required input for the next stage of the system: the RAG generation pipeline, which is responsible for summarization and embedding.
