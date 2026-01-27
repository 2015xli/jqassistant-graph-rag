# Design: LLMClient

## 1. Purpose and Role

The `LLMClient` module provides an abstract base class and a factory function for interacting with various Large Language Model (LLM) APIs. Its primary role is to offer a unified, consistent interface for generating text (specifically summaries in this project), abstracting away the specific implementation details, authentication, and request/response formats of different LLM providers.

This design allows the core application logic to remain independent of the chosen LLM, promoting flexibility and extensibility.

## 2. Workflow and Key Logic

### a. Abstract Base Class (`LlmClient`)

-   Defines the common interface that all concrete LLM clients must implement.
-   The core method is `generate_summary(self, prompt: str) -> str`, which takes a prompt string and returns the LLM's generated response.
-   Includes an `is_local` boolean property to indicate whether the client connects to a local LLM instance (e.g., Ollama) or a remote API.

### b. Concrete Implementations

Each concrete subclass of `LlmClient` is responsible for:

-   **Initialization**: Loading API keys (typically from environment variables), configuring API endpoints, and setting the specific model to use.
-   **API Interaction**: Handling the HTTP requests to the LLM provider's API, including setting headers, constructing the request payload (e.g., messages array for chat models), and parsing the response.
-   **Error Handling**: Catching network errors, API errors, and timeouts, and logging them appropriately.

Current implementations include:

-   **`OpenAiClient`**: Interacts with OpenAI's chat completion API.
-   **`DeepSeekClient`**: Interacts with DeepSeek's chat completion API.
-   **`OllamaClient`**: Interacts with a local Ollama instance, supporting both chat and generate endpoints. It also includes specific handling for local base URLs.
-   **`FakeLlmClient`**: A mock implementation that returns a static, hardcoded summary. This is invaluable for testing and development without incurring API costs or network dependencies.

### c. Factory Function (`get_llm_client`)

-   The `get_llm_client(api_name: str) -> LlmClient` function acts as a simple factory.
-   It takes a string `api_name` (e.g., "openai", "ollama", "fake") and returns an instantiated object of the corresponding `LlmClient` subclass.
-   It centralizes the logic for choosing which LLM client to use based on configuration.

## 3. Key Methods and Properties

-   **`LlmClient.generate_summary(prompt: str) -> str`**: The abstract method for generating a summary.
-   **`LlmClient.is_local: bool`**: Property indicating if the LLM is local.
-   **`get_llm_client(api_name: str) -> LlmClient`**: Factory function to retrieve an LLM client instance.
-   Specific client methods (e.g., `OllamaClient.generate_summary_chat`, `OllamaClient.generate_summary_reasoning`) for different interaction patterns if supported by the LLM.

## 4. Dependencies

-   `requests`: For making HTTP requests to remote LLM APIs.
-   `os`: For reading environment variables (API keys, model names, base URLs).
-   `logging`: For logging API interactions and errors.

## 5. Design Rationale

-   **Abstraction and Decoupling**: The primary benefit is decoupling the application's core summarization logic (in `NodeSummaryProcessor`) from the specifics of any particular LLM provider. This means the `NodeSummaryProcessor` can simply call `client.generate_summary()` without knowing if it's talking to OpenAI, Ollama, or a fake client.
-   **Extensibility**: Adding support for a new LLM API is straightforward: create a new subclass of `LlmClient`, implement its `generate_summary` method, and add it to the `get_llm_client` factory function. No changes are required in the rest of the application.
-   **Configurability**: The choice of LLM can be easily changed at runtime via command-line arguments or environment variables, making the system flexible for different deployment environments or cost considerations.
-   **Testability**: The `FakeLlmClient` is a critical design element for enabling fast, reliable, and cost-free unit and integration testing of the summarization logic without making actual API calls.
-   **Error Handling**: Centralizing API interaction in these clients ensures consistent error handling and logging for all LLM communications.
