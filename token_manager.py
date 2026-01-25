import logging
import re
from typing import List, Optional

import tiktoken

logger = logging.getLogger(__name__)

# Pre-compile the regex for finding special tokens
_SPECIAL_PATTERN = re.compile(r"<\|[^|]+?\|>")


def _sanitize_special_tokens(text: str) -> str:
    """
    Replaces special tokens like "<|im_start|>" with a format that
    prevents them from being treated as control tokens by the tokenizer.
    For example, "<|im_start|>" becomes "< |im_start| >".
    """
    return _SPECIAL_PATTERN.sub(lambda m: f"< |{m.group(0)[2:-2]}| >", text)


class TokenManager:
    """
    Manages tokenization, token counting, and context chunking logic to
    ensure that data sent to the LLM respects its context window size.
    """

    def __init__(
        self,
        max_context_token_size: int = 8192,
        token_encoding: str = "cl100k_base",
    ):
        """
        Initializes the TokenManager.
        Args:
            max_context_token_size: The maximum number of tokens allowed in the
                                    LLM's context window.
            token_encoding: The name of the tiktoken encoding to use.
        """
        self.max_context_token_size = max_context_token_size
        # Iterative chunking aims for chunks of about 50% of the max size
        self.iterative_chunk_size = int(0.5 * self.max_context_token_size)
        # Overlap is 10% of the chunk size to maintain context
        self.iterative_chunk_overlap = int(0.1 * self.iterative_chunk_size)

        try:
            self.tokenizer = tiktoken.get_encoding(token_encoding)
        except Exception:
            logger.warning(
                f"Could not load '{token_encoding}', "
                "falling back to 'p50k_base'."
            )
            self.tokenizer = tiktoken.get_encoding("p50k_base")

    def get_token_count(self, text: str) -> int:
        """
        Calculates the number of tokens in a given text.
        Args:
            text: The input string.
        Returns:
            The number of tokens.
        """
        safe_text = _sanitize_special_tokens(text)
        return len(self.tokenizer.encode(safe_text))

    def chunk_text_by_tokens(self, text: str) -> List[str]:
        """
        Splits a single large text into smaller, overlapping chunks based on
        the configured iterative chunk size.
        Args:
            text: The text to split.
        Returns:
            A list of text chunks.
        """
        safe_text = _sanitize_special_tokens(text)
        tokens = self.tokenizer.encode(safe_text)
        if not tokens:
            return []

        chunk_size = self.iterative_chunk_size
        overlap = self.iterative_chunk_overlap
        stride = chunk_size - overlap
        chunks = []
        i = 0

        while True:
            # If the remaining tokens can fit in one chunk, take them all
            if i + chunk_size >= len(tokens):
                chunks.append(tokens[i:])
                break

            chunks.append(tokens[i : i + chunk_size])
            i += stride

            # If the very last segment is tiny, merge it with the previous one
            # to avoid creating an unnaturally small final chunk.
            if (
                i + chunk_size >= len(tokens)
                and len(tokens) - i < (chunk_size * 0.5)
            ):
                chunks[-1] = tokens[i - stride :]
                break

        return [self.tokenizer.decode(chunk) for chunk in chunks]

    def chunk_summaries_by_tokens(self, summaries: List[str]) -> List[str]:
        """
        Groups a list of summary strings into larger chunks.
        Each chunk contains as many summaries as possible without exceeding the
        iterative chunk size and without splitting individual summaries.
        Args:
            summaries: A list of strings (e.g., child node summaries).
        Returns:
            A list of larger, concatenated summary strings.
        """
        if not summaries:
            return []

        separator = "; "
        sep_token_cost = self.get_token_count(separator)
        chunk_size = self.iterative_chunk_size

        # Pre-calculate token counts for each summary
        encoded_summaries = [
            (s, self.get_token_count(s)) for s in summaries
        ]

        chunks = []
        current_strings = []
        current_token_count = 0

        for summary_text, token_count in encoded_summaries:
            # If a single summary is larger than the chunk size, it becomes
            # its own chunk.
            if token_count > chunk_size:
                if current_strings:
                    chunks.append(separator.join(current_strings))
                chunks.append(summary_text)
                current_strings = []
                current_token_count = 0
                continue

            # Calculate the cost of adding the next summary
            cost = token_count
            if current_strings:
                cost += sep_token_cost

            # If adding it exceeds the budget, finalize the current chunk
            if current_token_count + cost > chunk_size:
                chunks.append(separator.join(current_strings))
                current_strings = [summary_text]
                current_token_count = token_count
            else:
                current_strings.append(summary_text)
                current_token_count += cost

        # Add the last remaining chunk
        if current_strings:
            chunks.append(separator.join(current_strings))

        return chunks
