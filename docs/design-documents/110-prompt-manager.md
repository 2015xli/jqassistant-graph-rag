# Design: PromptManager

## 1. Purpose and Role

The `PromptManager` is a stateless utility component responsible for centralizing all Large Language Model (LLM) prompt templates used throughout the GraphRAG system. Its primary role is to ensure consistency in prompt engineering, decouple prompt content from the application's core logic, and provide a clear interface for generating context-specific prompts for various summarization tasks.

## 2. Workflow and Key Logic

The `PromptManager` exposes a set of methods, each corresponding to a specific summarization scenario. These methods take relevant contextual data as input and return a fully formatted prompt string.

### a. Prompt Generation Methods

-   **`get_method_analysis_prompt(chunk, is_first_chunk, is_last_chunk, running_summary)`**: Generates prompts for analyzing a method's source code. It intelligently adapts the prompt based on whether the current `chunk` is the first, last, or a middle part of a larger method, facilitating iterative code analysis.
-   **`get_method_summary_prompt(method_name, code_analysis, callers, callees)`**: Creates a prompt for a single-shot contextual summary of a method, incorporating its technical analysis and summaries of its callers and callees.
-   **`get_iterative_method_summary_prompt(running_summary, relation_chunk, relation_type)`**: Generates prompts for iteratively refining a method summary by folding in chunks of caller or callee summaries.
-   **`get_type_summary_prompt(type_name, type_label, parent_summaries, member_summaries)`**: Creates a prompt for a single-shot summary of a type (class, interface, etc.), considering its inheritance and members.
-   **`get_iterative_type_summary_prompt(type_name, type_label, running_summary, relation_chunk, relation_type)`**: Generates prompts for iteratively refining a type summary by folding in chunks of parent or member summaries.
-   **`get_hierarchical_summary_prompt(node_type, node_name, context)`**: A generic prompt for single-shot hierarchical summarization (used by `SourceFileSummarizer`, `DirectorySummarizer`, `PackageSummarizer`, `ProjectSummarizer`), taking the node type, name, and aggregated child context.
-   **`get_iterative_hierarchical_prompt(node_type, node_name, running_summary, child_summaries_chunk)`**: Generates prompts for iteratively refining a hierarchical summary by folding in chunks of child summaries.

### b. Contextual Adaptation

Each prompt generation method is designed to:

-   Accept specific parameters that provide the necessary context for the LLM.
-   Construct a clear, concise, and effective prompt that guides the LLM to produce the desired output (e.g., "Provide a concise, one-paragraph technical analysis.").
-   Handle variations for iterative processing, ensuring the LLM understands the ongoing nature of the summarization task and can build upon previous responses.

## 3. Key Methods

-   All `get_*_prompt` methods listed above.

## 4. Dependencies

The `PromptManager` is a self-contained utility and has no external dependencies beyond standard Python libraries.

## 5. Design Rationale

-   **Centralization of Prompt Engineering**: All LLM prompts are stored and managed in a single location. This makes it easy to review, modify, and version control the prompts. It also ensures consistency in prompt style and instructions across the entire application.
-   **Decoupling**: It cleanly separates the "what to ask" (the prompt content) from the "how to ask" (the `LlmClient`'s API interaction) and the "when to ask" (the `NodeSummaryProcessor`'s summarization logic). This separation allows prompt engineers to refine prompts without requiring changes to the core application code.
-   **Maintainability and Extensibility**: If a prompt needs to be adjusted (e.g., to improve summary quality or adapt to a new LLM's characteristics), the change is localized to this module. Adding a new summarization task would involve adding a new prompt generation method here.
-   **Readability**: By abstracting prompt strings into dedicated methods, the core summarization logic in `NodeSummaryProcessor` becomes much cleaner and easier to read, as it doesn't contain large, inline prompt templates.
-   **Consistency in Iterative Prompts**: It ensures that the iterative summarization prompts (e.g., for chunking large code blocks or folding in child summaries) are consistently structured, guiding the LLM effectively through multi-step reasoning.
