"""
This module centralizes all LLM prompt templates for the GraphRAG system.
"""
from typing import List


class PromptManager:
    """
    Manages the generation of all prompts sent to the LLM.
    """

    def get_method_analysis_prompt(
        self,
        chunk: str,
        is_first_chunk: bool,
        is_last_chunk: bool,
        running_summary: str = "",
    ) -> str:
        """
        Returns the prompt for individual code analysis.
        Handles first, middle, and last chunks for iterative processing.
        """
        if is_first_chunk:
            if is_last_chunk:
                # The entire method fits in one chunk
                return (
                    "Summarize the purpose of this method based on its code. "
                    "Provide a concise, one-paragraph technical analysis. "
                    "Do not respond with your reasoning process, only the summary."
                    "\n\n```\n{chunk}\n```"
                )
            else:
                # This is the first chunk of a larger method
                return (
                    "Summarize this code, which is the beginning of a larger "
                    "method. Provide a concise, one-paragraph technical analysis. "
                    "Do not respond with your reasoning process, only the summary."
                    "\n\n```\n{chunk}\n```"
                )
        else:
            position_prompt = (
                "This is the end of the method body."
                if is_last_chunk
                else "The method body continues after this code."
            )
            return (
                "The summary of the first part of a large method so far is: \n"
                f"'{running_summary}'\n\n"
                f"Here is the next part of the code:\n```\n{chunk}\n```\n\n"
                f"{position_prompt}\n\n"
                "Please provide a new, single-paragraph summary that combines "
                "the previous summary with this new code. Do not respond with "
                "your reasoning process, only the summary."
            )

    def get_method_summary_prompt(
        self,
        method_name: str,
        code_analysis: str,
        callers: List[str],
        callees: List[str],
    ) -> str:
        """
        Generates the prompt for a contextual summary of a method's role.
        This is the single-shot version for when context fits in the window.
        """
        caller_text = "; ".join(callers) if callers else "None"
        callee_text = "; ".join(callees) if callees else "None"

        return (
            f"A method named '{method_name}' is technically analyzed as: "
            f"'{code_analysis}'.\n"
            "It is called by other methods with these responsibilities: "
            f"[{caller_text}].\n"
            "It calls other methods to accomplish these tasks: "
            f"[{callee_text}].\n\n"
            "Based on this full context, what is the high-level purpose of "
            f"this method in the overall system? Describe it in a concise "
            "paragraph. Do not respond with your reasoning process, only the summary."
        )

    def get_iterative_method_summary_prompt(
        self,
        running_summary: str,
        relation_chunk: str,
        relation_type: str,
    ) -> str:
        """
        Generates a prompt for iteratively refining a method summary.
        Args:
            running_summary: The summary built so far.
            relation_chunk: A chunk of caller or callee summaries.
            relation_type: Either 'callers' or 'callees'.
        """
        if relation_type == "callers":
            return (
                "A method's purpose is summarized as: "
                f"'{running_summary}'.\n"
                "It is used by other methods with the following responsibilities: "
                f"[{relation_chunk}].\n\n"
                "Refine the summary of the method's role in relation to its callers. "
                "Provide a new, single-paragraph summary. Do not respond with "
                "your reasoning process, only the summary."
            )
        elif relation_type == "callees":
            return (
                "So far, a method's role is summarized as: "
                f"'{running_summary}'.\n"
                "It accomplishes this by calling other methods for these purposes: "
                f"[{relation_chunk}].\n\n"
                "Provide a final, comprehensive summary of the method's "
                "overall purpose based on its callees. Provide a new, "
                "single-paragraph summary. Do not respond with your reasoning "
                "process, only the summary."
            )
        else:
            raise ValueError(f"Unknown relation_type: {relation_type}")

    def get_type_summary_prompt(
        self, type_name: str, type_label: str, parent_summaries: List[str], member_summaries: List[str]
    ) -> str:
        """
        Generates the prompt for a holistic summary of a type (class, interface, etc.).
        This is the single-shot version for when context fits in the window.
        """
        parent_text = (
            f"It inherits from or implements the following types: [{'; '.join(parent_summaries)}]."
            if parent_summaries
            else ""
        )
        member_text = (
            f"It contains members (methods, fields) with these responsibilities: [{'; '.join(member_summaries)}]."
            if member_summaries
            else ""
        )

        return (
            f"A {type_label} named '{type_name}' is defined. {parent_text} {member_text}\n\n"
            f"Based on its inheritance and members, what is the primary responsibility and role of the '{type_name}' {type_label} in the system? "
            "Describe it in a concise paragraph. Do not respond with your reasoning process, only the summary."
        )

    def get_iterative_type_summary_prompt(
        self,
        type_name: str,
        type_label: str,
        running_summary: str,
        relation_chunk: str,
        relation_type: str,
    ) -> str:
        """
        Generates a prompt for iteratively refining a type summary.
        """
        if relation_type == "parents":
            return (
                f"The summary for the {type_label} '{type_name}' is currently: '{running_summary}'.\n"
                "It inherits from or implements types with these roles: "
                f"[{relation_chunk}].\n\n"
                "Refine the summary to include the role of its inheritance. "
                "Provide a new, single-paragraph summary. Do not respond with "
                "your reasoning process, only the summary."
            )
        elif relation_type == "members":
            return (
                f"So far, the role of the {type_label} '{type_name}' is summarized as: '{running_summary}'.\n"
                "It implements members (methods, fields) to perform these functions: "
                f"[{relation_chunk}].\n\n"
                "Provide a final, comprehensive summary of the type's overall purpose. "
                "Provide a new, single-paragraph summary. Do not respond with "
                "your reasoning process, only the summary."
            )
        else:
            raise ValueError(f"Unknown relation_type for type summary: {relation_type}")

    def get_hierarchical_summary_prompt(
        self, node_type: str, node_name: str, context: str
    ) -> str:
        """
        Generates a prompt for a single-shot hierarchical summary.
        """
        prompts = {
            "SourceFile": f"Based on the following context, provide a concise summary for the source file named '{node_name}'.",
            "Directory": f"Based on the following context, provide a concise summary for the directory named '{node_name}'.",
            "Package": f"Based on the following context, provide a concise summary for the package named '{node_name}'.",
            "Project": f"Based on the following context, provide a concise summary for the project named '{node_name}'.",
        }
        if node_type not in prompts:
            raise ValueError(f"Unknown node_type for hierarchical summary: {node_type}")
        
        if not context:
            return f"Purpose of {node_type} '{node_name}' is unclear due to missing context."

        return f"""{prompts[node_type]}
Context:
{context}
Summary:
"""

    def get_iterative_hierarchical_prompt(
        self,
        node_type: str,
        node_name: str,
        running_summary: str,
        child_summaries_chunk: str,
    ) -> str:
        """
        Generates a prompt for iteratively refining a hierarchical summary.
        """
        return (
            f"The summary for the {node_type} '{node_name}' is currently: '{running_summary}'.\n"
            "It contains child components with the following responsibilities: "
            f"[{child_summaries_chunk}].\n\n"
            f"Refine the summary for the {node_type} '{node_name}' based on this new information. "
            "Provide a new, single-paragraph summary. Do not respond with "
            "your reasoning process, only the summary."
        )
