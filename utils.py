from typing import Any, Dict, List, Union
import os
import uuid
import json
import time

# For timestamp conversion: constant to convert seconds to milliseconds
MILLISECONDS = 1000

def validate_efo_id(efo_id: str) -> None:
    """
    Validate EFO ID format.
    
    Args:
        efo_id (str): EFO identifier to validate (e.g., "EFO_0000305")
    
    Raises:
        ValueError: If the EFO ID format is invalid
    """
    if not isinstance(efo_id, str):
        raise ValueError(f"EFO ID must be a string, got {type(efo_id)}")
    if not efo_id.startswith("EFO_") or not efo_id[4:].isdigit():
        raise ValueError(f"Invalid EFO ID format: {efo_id}. Must be in format 'EFO_XXXXXXX' where X is a digit.")


def write_large_result_to_file(output_dir: str, resp_url: str, items: Union[List[Any], Dict[str, Any]]) -> str:
    """
    Write large result items to a file.
    
    Args:
        output_dir (str): Directory to write the output file
        resp_url (str): API request URL to include in the output
        items (Union[List[Any], Dict[str, Any]]): Data to write to file
    
    Returns:
        str: Path to the created output file
    
    Raises:
        OSError: If directory creation or file writing fails
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        fname = f"large_result_{uuid.uuid4().hex}.json"
        fpath = os.path.join(output_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({"request_url": resp_url, "items": items}, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Complete result written to {fpath}")
        return fpath
    except OSError as e:
        raise OSError(f"Failed to write results to file: {e}")


def _remove_links(obj: Any) -> Any:
    """
    Recursively remove '_links' fields from dicts and lists.
    
    Args:
        obj (Any): Input object (dict, list, or any other type)
    
    Returns:
        Any: New object with all '_links' fields removed
    
    Examples:
        >>> _remove_links({"_links": {"self": "..."}, "data": 123})
        {"data": 123}
        >>> _remove_links([{"_links": {...}}, {"data": 123}])
        [{"data": 123}, {"data": 123}]
    """
    if isinstance(obj, dict):
        return {k: _remove_links(v) for k, v in obj.items() if k != "_links"}
    elif isinstance(obj, list):
        return [_remove_links(x) for x in obj]
    return obj 

def get_default_output_dir() -> str:
    """
    Get the default output directory for large results.
    Uses environment variable or tests/output/success for test output, otherwise /tmp.
    
    Returns:
        str: Path to the default output directory
    """
    return os.environ.get("TEST_OUTPUT_SUCCESS_DIR", "/tmp")

def create_empty_response(request_url: str, max_items_in_memory: int, return_only_sig: bool) -> Dict[str, Any]:
    """
    Create an empty response with standard metadata.
    
    Args:
        request_url (str): The URL of the request
        max_items_in_memory (int): Maximum items to keep in memory
        return_only_sig (bool): Whether only significant results are returned
    Returns:
        Dict[str, Any]: Standard empty response structure
    """
    return {
        "request_url": request_url,
        "items": [],
        "total_count": 0,
        "is_complete": True,
        "metadata": {
            "subset_size": 0,
            "max_items_in_memory": max_items_in_memory,
            "return_only_sig": return_only_sig
        }
    }

def format_error(resp: Any) -> Dict[str, Any]:
    """
    Format error response in a standard way.
    
    Args:
        resp: Response object with status_code, url, and text/json attributes
    Returns:
        Dict[str, Any]: Formatted error response
    """
    try:
        err = resp.json()
    except Exception:
        err = {"error": "Invalid JSON", "message": resp.text}
    err["status"] = resp.status_code
    err["request_url"] = resp.url
    err["timestamp"] = int(time.time() * MILLISECONDS)  # Convert to milliseconds
    return err 