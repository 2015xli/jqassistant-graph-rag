# Design: TokenManager

## 1. Purpose and Role

The `TokenManager` is a critical utility component responsible for managing all interactions related to the Large Language Model's (LLM) context window. LLMs have a fixed limit on the number of tokens (pieces of words) they can process in a single request. The `TokenManager`'s primary role is to provide the tools to count tokens and, more importantly, to split or "chunk" large pieces of text into smaller segments that respect this limit.

It encapsulates the specific logic for tokenization and chunking, allowing higher-level components like the `NodeSummaryProcessor` to handle arbitrarily large contexts without needing to be aware of the low-level details of token management.

## 2. Key Logic and Functionality

### a. Tokenization

1.  **Tokenizer Initialization**: The manager is initialized with a specific token encoding (e.g., `cl100k_base`, used by modern OpenAI models). It uses the `tiktoken` library to load the appropriate tokenizer.
2.  **Token Counting (`get_token_count`)**: This method takes a string of text and returns the number of tokens it represents. This is the fundamental operation used to check if a given context will fit into the LLM's context window.
3.  **Special Token Handling**: The tokenizer can sometimes misinterpret special tokens used in prompts (like `<|im_start|>`). The `TokenManager` includes logic to sanitize these tokens before counting, ensuring an accurate token count.

### b. Context Chunking

The `TokenManager` provides two main strategies for chunking large contexts, designed for different use cases.

1.  **`chunk_text_by_tokens`**: This method is designed for splitting a single, large, contiguous block of text (like a very long source code file).
    *   It tokenizes the entire text.
    *   It then slides a window across the list of tokens, creating chunks of a configured size (e.g., 4096 tokens).
    *   To maintain context between chunks, the windows are overlapped by a certain amount (e.g., 400 tokens). The end of one chunk is the same as the beginning of the next one.
    *   This strategy is ideal for the iterative refinement of a summary from a single source.

2.  **`chunk_summaries_by_tokens`**: This method is designed for grouping a list of many smaller texts (like the summaries of child nodes).
    *   Its goal is to create a few large chunks from many small summaries, rather than splitting the summaries themselves.
    *   It iterates through the list of summaries, adding them one by one to the current chunk.
    *   It keeps a running total of the token count for the current chunk.
    *   Once adding the next summary would exceed the configured chunk size, it finalizes the current chunk and starts a new one.
    *   This strategy is used to feed child context to the `NodeSummaryProcessor`'s hierarchical summarization logic efficiently.

## 3. Key Methods

-   `__init__(self, max_context_token_size, ...)`: The constructor configures the maximum token limits and initializes the `tiktoken` tokenizer.
-   `get_token_count(text)`: Returns the number of tokens in a string.
-   `chunk_text_by_tokens(text)`: Splits a single large text into overlapping chunks of tokens.
-   `chunk_summaries_by_tokens(summaries)`: Groups a list of smaller summary strings into larger chunks without splitting the individual summaries.

## 4. Dependencies

The `TokenManager` is a low-level utility with only one external dependency:
-   `tiktoken`: The Python library used for high-performance tokenization.

## 5. Design Rationale

-   **Encapsulation of a Core Constraint**: The LLM context window is a fundamental and universal constraint. By encapsulating all logic for dealing with this constraint in a single component, the rest of the system is simplified. The `NodeSummaryProcessor` can simply ask the `TokenManager` to "chunk this context" without needing to know how the chunking is done.
-   **Separation of Strategy**: The component provides different chunking strategies (`chunk_text_by_tokens` vs. `chunk_summaries_by_tokens`) tailored to different kinds of input. This is a clean design that recognizes that a single block of text and a list of discrete summaries should be handled differently.
-   **Configurability**: The chunk sizes and overlap are configurable during initialization. This makes it easy to adapt the system to different LLMs that may have different context window sizes in the future, without changing the core processing logic.
-   **Accuracy**: By using the official `tiktoken` library, the token counts are accurate for the target models, preventing off-by-one errors and unexpected API failures due to exceeding the context limit.
