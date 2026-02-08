"""Tool result truncation to prevent context overflow"""

import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Maximum characters for different result types
MAX_FILE_LIST_LENGTH = 50000  # ~12,500 tokens (4 chars/token)
MAX_SEARCH_RESULTS_LENGTH = 100000  # ~25,000 tokens
MAX_SINGLE_FILE_LENGTH = 200000  # ~50,000 tokens
MAX_GENERIC_RESULT_LENGTH = 150000  # ~37,500 tokens

# Truncation messages
TRUNCATION_MESSAGE = "\n\n[... Content truncated to prevent context overflow. {} items removed ...]"
FILE_LIST_TRUNCATION = "\n\n[... File list truncated. Showing {} of {} total files. Use more specific patterns or filters to reduce results ...]"


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for text.

    Uses conservative estimate of 4 characters per token.
    """
    return len(text) // 4


def truncate_tool_result(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligently truncate tool results to prevent context overflow.

    Args:
        tool_name: Name of the tool that produced the result
        result: Tool result dictionary

    Returns:
        Truncated result dictionary with metadata about truncation
    """
    if not result or not isinstance(result, dict):
        return result

    # Don't truncate error responses (they're usually small)
    if not result.get("success", True):
        return result

    result_copy = result.copy()
    data = result_copy.get("data", {})

    if not data:
        return result_copy

    truncated = False
    truncation_info = {}

    # Handle file listing tools (glob, list_files)
    if tool_name in ("glob", "list_files"):
        files = data.get("files", [])
        if isinstance(files, list) and len(files) > 0:
            # Calculate size
            files_json = json.dumps(files, ensure_ascii=False)
            if len(files_json) > MAX_FILE_LIST_LENGTH:
                # Truncate to reasonable number
                max_files = 100  # Show at most 100 files
                original_count = len(files)
                truncated_files = files[:max_files]

                data["files"] = truncated_files
                data["count"] = len(truncated_files)
                data["total_count"] = original_count
                data["truncated"] = True
                data["truncation_reason"] = (
                    f"File list truncated to prevent context overflow. Showing {max_files} of {original_count} total files."
                )

                truncated = True
                truncation_info = {
                    "original_count": original_count,
                    "truncated_count": len(truncated_files),
                    "items_removed": original_count - len(truncated_files),
                }

                logger.warning(
                    f"Truncated {tool_name} result: {original_count} -> {len(truncated_files)} files "
                    f"(saved ~{estimate_token_count(files_json) // 1000}K tokens)"
                )

    # Handle search tools (grep, search_files)
    elif tool_name in ("grep", "search_files"):
        results = data.get("results", [])
        if isinstance(results, list) and len(results) > 0:
            # Calculate size
            results_json = json.dumps(results, ensure_ascii=False)
            if len(results_json) > MAX_SEARCH_RESULTS_LENGTH:
                # Truncate to reasonable number
                max_results = 200  # Show at most 200 matches
                original_count = len(results)
                truncated_results = results[:max_results]

                data["results"] = truncated_results
                data["match_count"] = len(truncated_results)
                data["total_matches"] = data.get("total_matches", original_count)
                data["truncated"] = True
                data["truncation_reason"] = (
                    f"Search results truncated. Showing {max_results} of {original_count} matches."
                )

                truncated = True
                truncation_info = {
                    "original_count": original_count,
                    "truncated_count": len(truncated_results),
                    "items_removed": original_count - len(truncated_results),
                }

                logger.warning(
                    f"Truncated {tool_name} result: {original_count} -> {len(truncated_results)} matches "
                    f"(saved ~{estimate_token_count(results_json) // 1000}K tokens)"
                )

    # Handle file reading tools
    elif tool_name in ("read_file",):
        content = data.get("content", "")
        if isinstance(content, str) and len(content) > MAX_SINGLE_FILE_LENGTH:
            original_length = len(content)
            # Keep first portion and add truncation message
            truncated_content = content[:MAX_SINGLE_FILE_LENGTH]
            # Find last complete line
            last_newline = truncated_content.rfind("\n")
            if last_newline > 0:
                truncated_content = truncated_content[:last_newline]

            truncated_content += f"\n\n[... Content truncated at {len(truncated_content)} characters. Original file is {original_length} characters. Use offset/limit parameters to read specific portions ...]"

            data["content"] = truncated_content
            data["truncated"] = True
            data["original_size"] = original_length
            data["truncation_reason"] = "File content truncated to prevent context overflow."

            truncated = True
            truncation_info = {
                "original_size": original_length,
                "truncated_size": len(truncated_content),
                "bytes_removed": original_length - len(truncated_content),
            }

            logger.warning(
                f"Truncated {tool_name} result: {original_length} -> {len(truncated_content)} chars "
                f"(saved ~{(original_length - len(truncated_content)) // 4000}K tokens)"
            )

    # Handle AST tools (ast_extract, ast_search, ast_analyze)
    elif tool_name in ("ast_extract", "ast_search", "ast_analyze"):
        extracted = data.get("extracted", [])
        if isinstance(extracted, list) and len(extracted) > 0:
            # Calculate size
            extracted_json = json.dumps(extracted, ensure_ascii=False)
            max_structures = 150  # Limit to 150 structures

            if len(extracted_json) > MAX_SEARCH_RESULTS_LENGTH or len(extracted) > max_structures:
                original_count = len(extracted)
                truncated_extracted = extracted[:max_structures]

                data["extracted"] = truncated_extracted
                data["structure_count"] = len(truncated_extracted)
                data["total_structures"] = original_count
                data["truncated"] = True
                data["truncation_reason"] = (
                    f"AST results truncated to prevent context overflow. "
                    f"Showing {len(truncated_extracted)} of {original_count} structures. "
                    f"Use pattern filtering or narrow your search path to get specific results."
                )

                truncated = True
                truncation_info = {
                    "original_count": original_count,
                    "truncated_count": len(truncated_extracted),
                    "items_removed": original_count - len(truncated_extracted),
                }

                logger.warning(
                    f"Truncated {tool_name} result: {original_count} -> {len(truncated_extracted)} structures "
                    f"(saved ~{estimate_token_count(extracted_json) // 1000}K tokens)"
                )

    # Generic truncation for any large result
    else:
        # Convert to JSON to check total size
        try:
            result_json = json.dumps(result_copy, ensure_ascii=False)
            if len(result_json) > MAX_GENERIC_RESULT_LENGTH:
                logger.warning(
                    f"Large result from {tool_name}: {len(result_json)} chars "
                    f"(~{estimate_token_count(result_json) // 1000}K tokens). "
                    f"Consider implementing specific truncation logic for this tool."
                )

                # Generic truncation: limit string fields
                truncated = _truncate_dict_strings(data, MAX_GENERIC_RESULT_LENGTH // 2)
                if truncated:
                    data["truncated"] = True
                    data["truncation_reason"] = "Result truncated due to large size."
        except (TypeError, ValueError) as e:
            logger.debug(f"Could not estimate result size: {e}")

    # Add truncation metadata if truncated
    if truncated and truncation_info:
        result_copy["truncation_info"] = truncation_info

    result_copy["data"] = data
    return result_copy


def _truncate_dict_strings(
    data: Dict[str, Any], max_total_length: int, current_length: int = 0
) -> bool:
    """
    Recursively truncate string values in a dictionary.

    Returns True if any truncation occurred.
    """
    truncated = False
    max_str_length = 10000  # Max length for individual strings

    for key, value in data.items():
        if isinstance(value, str) and len(value) > max_str_length:
            data[key] = value[:max_str_length] + f"\n[... truncated, original length: {len(value)}]"
            truncated = True
        elif isinstance(value, dict):
            if _truncate_dict_strings(value, max_total_length, current_length):
                truncated = True
        elif isinstance(value, list):
            # Truncate lists if they're too large
            if len(value) > 500:
                data[key] = value[:500]
                truncated = True

    return truncated


def should_truncate_proactively(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze tool arguments and suggest better limits to prevent large results.

    Args:
        tool_name: Name of the tool
        arguments: Tool arguments

    Returns:
        Modified arguments with safer limits, or original arguments
    """
    args_copy = arguments.copy()
    modified = False

    # Limit glob results
    if tool_name == "glob":
        if "max_results" not in args_copy or args_copy.get("max_results", 500) > 200:
            args_copy["max_results"] = 200
            modified = True

        # Check for overly broad patterns
        pattern = args_copy.get("pattern", "")
        if pattern in ("*", "**/*", "**"):
            logger.warning(
                f"Very broad glob pattern '{pattern}' may return excessive results. "
                "Consider using more specific patterns like '**/*.py' or 'src/**/*'"
            )

    # Limit grep results
    elif tool_name == "grep":
        if "head_limit" not in args_copy or args_copy.get("head_limit", 50) > 100:
            args_copy["head_limit"] = 100
            modified = True

    # Warn about read_file without limits on potentially large files
    elif tool_name == "read_file":
        if "limit" not in args_copy:
            # Could add size checking here if we wanted
            pass

    if modified:
        logger.debug(f"Modified {tool_name} arguments to prevent large results: {args_copy}")

    return args_copy
