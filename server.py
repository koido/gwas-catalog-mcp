from fastmcp import FastMCP
from typing import Optional, List, Dict, Any
import requests
import os
import json
from datetime import datetime
from utils import (
    write_large_result_to_file,
    _remove_links,
    get_default_output_dir,
    create_empty_response,
    format_error,
    validate_efo_id,
)

# instantiate server
mcp = FastMCP("GWAS_catalog")

# Base URL for GWAS Catalog REST API
BASE_URL = "https://www.ebi.ac.uk/gwas/rest/api"

# Success status code
SUCCESS_STATUS_CODE = 200

# Pagination for GWAS Catalog REST API: maximum number of items per request (recommended upper limit)
GWAS_API_PAGE_SIZE = 1000

# Genome-wide significance threshold
GWAS_THRESHOLD = 5e-8

# Helper: GET single object
def _get_object(path: str, remove_links: bool = True) -> Dict[str, Any]:
    """
    Helper function to get a single object from the API at the specified path.
    Args:
        path (str): API path.
        remove_links (bool): If True (default), remove all '_links' fields from the output.
    Returns:
        Dict[str, Any]: Response data.
    """
    url = f"{BASE_URL}/{path}"
    resp = requests.get(url)
    if resp.status_code == SUCCESS_STATUS_CODE:
        data = resp.json()
        if isinstance(data, dict):
            data["status"] = resp.status_code
            data["request_url"] = resp.url
        if remove_links:
            data = _remove_links(data)
        return data
    return format_error(resp)

def _extract_embedded_items(data: Dict[str, Any], key: str = "associations") -> List[Dict[str, Any]]:
    """
    Extract items from the _embedded field in the API response.
    Args:
        data (Dict[str, Any]): API response data
        key (str): Key to extract from _embedded (default: "associations")
    Returns:
        List[Dict[str, Any]]: List of items
    """
    if not isinstance(data, dict):
        return []
    
    embedded = data.get("_embedded", {})
    if not isinstance(embedded, dict):
        return []
    
    items = embedded.get(key, [])
    
    # Handle Summary Statistics API response format where items are in a dictionary
    if isinstance(items, dict) and all(str(k).isdigit() for k in items.keys()):
        return list(items.values())
    
    return items if isinstance(items, list) else []

def _add_gwas_significance(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Add is_gwas_significant flag to items based on their p-value.
    
    Args:
        items (List[Dict[str, Any]]): List of items containing p-values
    Returns:
        List[Dict[str, Any]]: Items with is_gwas_significant flag added
    """
    if not items:
        return items
        
    for item in items:
        try:
            # Try both pvalue and p_value fields
            p_str = item.get('pvalue') or item.get('p_value')
            if p_str is not None:
                p = float(p_str)
                item['is_gwas_significant'] = p <= GWAS_THRESHOLD
            else:
                item['is_gwas_significant'] = None
        except (ValueError, TypeError):
            item['is_gwas_significant'] = None
    
    return items

def _process_api_response(
    items: List[Dict[str, Any]],
    request_url: str,
    max_items_in_memory: int,
    return_only_sig: bool,
    remove_links: bool = True,
    output_dir: str = None,
    force_to_file: bool = False,
    force_no_file: bool = False,
    skip_gwas_significance: bool = False
) -> Dict[str, Any]:
    """
    Process API response items with standard filtering and metadata.
    
    Args:
        items (List[Dict[str, Any]]): List of items from API response
        request_url (str): The URL of the request
        max_items_in_memory (int): Maximum items to keep in memory
        return_only_sig (bool): Whether only significant results are returned
        remove_links (bool): Whether to remove _links fields
        output_dir (str): Directory for file output
        force_to_file (bool): Force file output
        force_no_file (bool): Never write to file
        skip_gwas_significance (bool): Skip GWAS significance processing
    Returns:
        Dict[str, Any]: Processed response with standard structure
    """
    if not items:
        empty_resp = create_empty_response(request_url, max_items_in_memory, return_only_sig)
        if not skip_gwas_significance:
            empty_resp["metadata"]["total_items"] = 0
            empty_resp["metadata"]["significant_items"] = 0
        return empty_resp

    total_items = len(items)
    
    # Base metadata that's always included
    metadata = {
        "subset_size": 0,  # Will be updated later
        "max_items_in_memory": max_items_in_memory
    }
    
    # Add GWAS significance flag and filter if needed
    if not skip_gwas_significance:
        _add_gwas_significance(items)
        sig_count = sum(1 for item in items if item.get("is_gwas_significant", False))
        metadata.update({
            "return_only_sig": return_only_sig,
            "total_items": total_items,
            "significant_items": sig_count
        })
        if return_only_sig:
            items = [item for item in items if item.get("is_gwas_significant", False)]
            if not items:
                empty_resp = create_empty_response(request_url, max_items_in_memory, return_only_sig)
                empty_resp["metadata"].update(metadata)
                return empty_resp
    
    # Remove _links if requested
    if remove_links:
        items = _remove_links(items)
    
    # Handle large results
    total_items_aft_process = len(items)
    if (total_items_aft_process > max_items_in_memory and not force_no_file) or force_to_file:
        output_file = write_large_result_to_file(
            output_dir or get_default_output_dir(),
            request_url,
            items
        )
        metadata["subset_size"] = len(items[:max_items_in_memory])
        metadata["output_file"] = output_file
        return {
            "request_url": request_url,
            "items": items[:max_items_in_memory],
            "total_items_aft_process": total_items_aft_process,
            "is_complete": False,
            "metadata": metadata
        }
    
    metadata["subset_size"] = total_items_aft_process
    return {
        "request_url": request_url,
        "items": items,
        "total_items_aft_process": total_items_aft_process,
        "is_complete": True,
        "metadata": metadata
    }

@mcp.tool(
    name="get_study",
    description="[GWAS Catalog API] Retrieve detailed study information by study ID. Input: studyId (str): GWAS Catalog study identifier (e.g., 'GCST000001'), remove_links (bool, optional): If True (default), remove all '_links' fields from the output. Output: Dict[str, Any] containing study metadata and HTTP status code."
)
def get_study(studyId: str, remove_links: bool = True) -> Dict[str, Any]:
    """
    Retrieve detailed study information by study ID.

    Input:
        studyId (str): GWAS Catalog study identifier (e.g., "GCST000001").
        remove_links (bool, optional): If True (default), remove all '_links' fields from the output. If False, include '_links'.
    Output:
        Dict[str, Any]: JSON response containing study metadata and HTTP status code.
    """
    return _get_object(f"studies/{studyId}", remove_links=remove_links)

@mcp.tool(
    name="get_association",
    description="[GWAS Catalog API] Retrieve detailed association information by association ID. Input: associationId (str): GWAS Catalog association identifier, remove_links (bool, optional): If True (default), remove all '_links' fields from the output. Output: Dict[str, Any] containing association fields and HTTP status code."
)
def get_association(associationId: str, remove_links: bool = True) -> Dict[str, Any]:
    """
    Retrieve detailed association information by association ID.

    Input:
        associationId (str): GWAS Catalog association identifier.
        remove_links (bool, optional): If True (default), remove all '_links' fields from the output. If False, include '_links'.
    Output:
        Dict[str, Any]: JSON response containing association fields and HTTP status code.
    """
    data = _get_object(f"associations/{associationId}", remove_links=remove_links)
    if isinstance(data, dict) and "error" not in data:
        data["association_id"] = associationId
    return data

@mcp.tool(
    name="get_variant",
    description="[GWAS Catalog API] Retrieve detailed variant information by variant ID. Input: variantId (str): Single nucleotide polymorphism identifier (e.g., 'rs123'), remove_links (bool, optional): If True (default), remove all '_links' fields from the output. Output: Dict[str, Any] containing variant annotations and HTTP status code."
)
def get_variant(variantId: str, remove_links: bool = True) -> Dict[str, Any]:
    """
    Retrieve detailed variant information by variant ID.

    Input:
        variantId (str): Single nucleotide polymorphism identifier (e.g., "rs123").
        remove_links (bool, optional): If True (default), remove all '_links' fields from the output. If False, include '_links'.
    Output:
        Dict[str, Any]: JSON response containing variant annotations and HTTP status code.
    """
    return _get_object(f"singleNucleotidePolymorphisms/{variantId}", remove_links=remove_links)

@mcp.tool(
    name="get_trait",
    description="[GWAS Catalog API] Retrieve trait information by EFO trait ID. Input: efoId (str): EFO trait identifier (e.g., 'EFO_0000305'), remove_links (bool, optional): If True (default), remove all '_links' fields from the output. Output: Dict[str, Any] containing trait details and HTTP status code."
)
def get_trait(efoId: str, remove_links: bool = True) -> Dict[str, Any]:
    """
    Retrieve trait information by EFO trait ID.

    Input:
        efoId (str): EFO trait identifier (e.g., "EFO_0000305").
        remove_links (bool, optional): If True (default), remove all '_links' fields from the output. If False, include '_links'.
    Output:
        Dict[str, Any]: JSON response containing trait details and HTTP status code.
    """
    data = _get_object(f"efoTraits/{efoId}", remove_links=remove_links)
    # add trait_id for consistency with API
    if isinstance(data, dict) and "error" not in data:
        data["trait_id"] = efoId
    return data

@mcp.tool(
    name="search_variants_in_region",
    description="[GWAS Catalog API] Search for associations by genomic region (GRCh38/hg38) and optional EFO trait filter. By default, returns only genome-wide significant associations (p<5e-8). Input: chromosome (str): Chromosome (e.g., '1'), start (int): GRCh38 base-pair start position, end (int): GRCh38 base-pair end position, efo_id (str, optional): EFO trait ID (e.g., 'EFO_0000305'), return_only_sig (bool, optional): If True (default), return only genome-wide significant associations, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: Dict containing: 'request_url': API request URL, 'items': List of associations (limited to max_items_in_memory), 'total_count': Total number of results, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with 'subset_size', 'max_items_in_memory', and 'return_only_sig'. IMPORTANT: Always check 'metadata' and 'is_complete' to ensure you have all the data you need. If 'is_complete' is False, the complete dataset has been saved to 'output_file'."
)
def search_variants_in_region(
    chromosome: str,
    start: int,
    end: int,
    efo_id: str = None,
    return_only_sig: bool = True,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = "/tmp",
    force_no_file: bool = False,
    remove_links: bool = True
) -> Any:
    """
    Search for associations by genomic region and optional EFO trait filter.
    By default, returns only genome-wide significant associations (p<5e-8).

    Input:
        chromosome (str): Chromosome (e.g., "1").
        start (int): GRCh38 (hg38) base-pair start position.
        end (int): GRCh38 (hg38) base-pair end position.
        efo_id (str, optional): EFO trait ID (e.g., "EFO_0000305").
        return_only_sig (bool, optional): If True (default), return only genome-wide significant associations.
        remove_links (bool, optional): If True (default), remove all '_links' fields from the output. If False, include '_links'.
    Output:
        List[Dict[str, Any]]: List of association records (_embedded.associations).
    Raises:
        ValueError: If efo_id is provided and not a valid EFO ID format.
    """
    params = {"size": GWAS_API_PAGE_SIZE, "chromosome": chromosome, "bp_start": start, "bp_end": end}
    if efo_id:
        validate_efo_id(efo_id)
        params["efoTrait"] = efo_id
    
    resp = requests.get(f"{BASE_URL}/associations", params=params)
    if resp.status_code != SUCCESS_STATUS_CODE:
        return create_empty_response(resp.url, max_items_in_memory, return_only_sig)
    
    items = _extract_embedded_items(resp.json())
    return _process_api_response(
        items=items,
        request_url=resp.url,
        max_items_in_memory=max_items_in_memory,
        return_only_sig=return_only_sig,
        remove_links=remove_links,
        output_dir=output_dir,
        force_to_file=force_to_file,
        force_no_file=force_no_file
    )

@mcp.tool(
    name="get_variants_from_efo_ids",
    description="[GWAS Catalog API] Batch search for variants associated with each EFO trait ID in the provided list. By default, returns only genome-wide significant associations (p<5e-8). Input: efo_ids (List[str]): List of EFO trait identifiers (e.g., ['EFO_0001360', 'EFO_0004340']), return_only_sig (bool, optional): If True (default), return only genome-wide significant associations, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: Dict containing: 'request_url': API request URL, 'items': Dict mapping EFO IDs to their respective results, where each result is a Dict containing {'request_url': API request URL specific to the EFO ID, 'items': List of associations for that EFO ID (limited to max_items_in_memory), 'total_count': Number of associations for that EFO ID, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with EFO ID-specific 'subset_size', 'max_items_in_memory', and 'return_only_sig'}, 'total_count': Total number of results across all EFO IDs, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with 'subset_size' (sum of all EFO IDs), 'max_items_in_memory', and 'return_only_sig'. IMPORTANT: Always check 'metadata' and 'is_complete' for both the overall result and each EFO ID's result to ensure you have all the data you need. If 'is_complete' is False for any EFO ID, that EFO ID's complete dataset has been saved to its own 'output_file'."
)
def get_variants_from_efo_ids(
    efo_ids: List[str],
    return_only_sig: bool = True,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = "/tmp",
    force_no_file: bool = False,
    remove_links: bool = True
) -> Dict[str, Any]:
    """
    Batch search for variants associated with each EFO trait ID in the provided list.
    By default, returns only genome-wide significant associations (p<5e-8).

    Input:
        efo_ids (List[str]): List of EFO trait identifiers (e.g., ["EFO_0001360", "EFO_0004340"]).
        return_only_sig (bool, optional): If True (default), return only genome-wide significant associations.
        max_items_in_memory (int): Threshold for in-memory return. Default 5000.
        force_to_file (bool): Force file output. Default False.
        output_dir (str): Output directory for large results. Default "/tmp".
        force_no_file (bool): Never write to file. Default False.
        remove_links (bool): If True (default), remove all '_links' fields from the output.
    Output:
        Dict[str, Dict[str, Any]]: Mapping EFO trait ID to list of association records.
    Raises:
        ValueError: If any EFO ID does not match the EFO format (EFO_XXXXXXX).
    """
    # Validate EFO ID format
    for efo_id in efo_ids:
        validate_efo_id(efo_id)

    results = {}
    for efo_id in efo_ids:
        resp = requests.get(f"{BASE_URL}/associations", params={"efoTrait": efo_id, "size": GWAS_API_PAGE_SIZE})
        if resp.status_code != SUCCESS_STATUS_CODE:
            results[efo_id] = create_empty_response(resp.url, max_items_in_memory, return_only_sig)
            continue
        
        items = _extract_embedded_items(resp.json())
        results[efo_id] = _process_api_response(
            items=items,
            request_url=resp.url,
            max_items_in_memory=max_items_in_memory,
            return_only_sig=return_only_sig,
            remove_links=remove_links,
            output_dir=output_dir,
            force_to_file=force_to_file,
            force_no_file=force_no_file
        )
    return results

@mcp.tool(
    name="trait_variant_ranking",
    description="[GWAS Catalog API] Rank variants by p-value (ascending order) for a specific EFO trait. By default, returns only genome-wide significant associations (p<5e-8). Input: efo_id (str): EFO trait ID, top_n (int, optional): Number of top records to return (default: 10), return_only_sig (bool, optional): If True (default), return only genome-wide significant associations, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: Dict containing: 'request_url': API request URL, 'items': List of top N associations sorted by p-value in ascending order (lowest p-value first, limited to max_items_in_memory), where each association includes at minimum 'variant_id', 'pvalue', and trait-specific statistics, 'total_count': Total number of results before top N filtering, 'is_complete': Boolean indicating if all results were available for ranking (True if total results <= max_items_in_memory), 'metadata': Dict with 'subset_size', 'max_items_in_memory', and 'return_only_sig'. IMPORTANT: Always check 'metadata' and 'is_complete' to ensure the ranking was performed on the complete dataset. If 'is_complete' is False, the complete dataset has been saved to 'output_file', but the returned ranking may not represent the true top N across all data."
)
def trait_variant_ranking(
    efo_id: str,
    top_n: int = 10,
    return_only_sig: bool = True,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = "/tmp",
    force_no_file: bool = False,
    remove_links: bool = True
) -> Any:
    """
    Rank variants by p-value for a specific EFO trait and return top N.
    By default, returns only genome-wide significant associations (p<5e-8).

    Input:
        efo_id (str): EFO trait ID.
        top_n (int): Number of top records to return.
        return_only_sig (bool, optional): If True (default), return only genome-wide significant associations.
    Output:
        List[Dict[str, Any]]: Top-N association records sorted by p-value.
    Raises:
        ValueError: If efo_id is not a valid EFO ID format.
    """
    validate_efo_id(efo_id)
    resp = requests.get(f"{BASE_URL}/associations", params={"efoTrait": efo_id, "size": GWAS_API_PAGE_SIZE})
    if resp.status_code != SUCCESS_STATUS_CODE:
        return create_empty_response(resp.url, max_items_in_memory, return_only_sig)
    
    items = _extract_embedded_items(resp.json())
    if not items:
        return create_empty_response(resp.url, max_items_in_memory, return_only_sig)
    
    # Sort by p-value before processing
    sorted_items = sorted([v for v in items if v.get("pvalue")], key=lambda x: float(x.get("pvalue", float("inf"))))[:top_n]
    
    return _process_api_response(
        items=sorted_items,
        request_url=resp.url,
        max_items_in_memory=max_items_in_memory,
        return_only_sig=return_only_sig,
        remove_links=remove_links,
        output_dir=output_dir,
        force_to_file=force_to_file,
        force_no_file=force_no_file
    )

@mcp.tool(
    name="get_study_associations",
    description="[GWAS Catalog API] Retrieve all associations for a given study ID. By default, returns only genome-wide significant associations (p<5e-8). Input: studyId (str): GWAS Catalog study identifier, return_only_sig (bool, optional): If True (default), return only genome-wide significant associations, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: Dict containing: 'request_url': API request URL, 'items': List of association summaries (limited to max_items_in_memory), 'total_count': Total number of associations, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with 'subset_size', 'max_items_in_memory', and 'return_only_sig'. IMPORTANT: Always check 'metadata' and 'is_complete' to ensure you have all the data you need. If 'is_complete' is False, the complete dataset has been saved to 'output_file'."
)
def get_study_associations(
    studyId: str,
    return_only_sig: bool = True,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = "/tmp",
    force_no_file: bool = False,
    remove_links: bool = True
) -> Any:
    """
    Retrieve all associations for a given study ID.
    By default, returns only genome-wide significant associations (p<5e-8).

    Input:
        studyId (str): GWAS Catalog study identifier.
        return_only_sig (bool, optional): If True (default), return only genome-wide significant associations.
    Output:
        List[Dict[str, Any]]: List of association summaries.
    """
    resp = requests.get(f"{BASE_URL}/studies/{studyId}/associations")
    if resp.status_code != SUCCESS_STATUS_CODE:
        return create_empty_response(resp.url, max_items_in_memory, return_only_sig)
    
    items = _extract_embedded_items(resp.json())
    return _process_api_response(
        items=items,
        request_url=resp.url,
        max_items_in_memory=max_items_in_memory,
        return_only_sig=return_only_sig,
        remove_links=remove_links,
        output_dir=output_dir,
        force_to_file=force_to_file,
        force_no_file=force_no_file
    )

@mcp.tool(
    name="get_trait_studies",
    description="[GWAS Catalog API] Retrieve studies associated with a specific EFO trait ID. Input: efoId (str): EFO trait identifier, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: Dict containing: 'request_url': API request URL, 'items': List of study summaries (limited to max_items_in_memory), 'total_count': Total number of studies, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with 'subset_size' and 'max_items_in_memory'. IMPORTANT: Always check 'metadata' and 'is_complete' to ensure you have all the data you need. If 'is_complete' is False, the complete dataset has been saved to 'output_file'."
)
def get_trait_studies(
    efoId: str,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = "/tmp",
    force_no_file: bool = False,
    remove_links: bool = True
) -> Any:
    """
    Retrieve studies associated with a specific EFO trait ID.

    Input:
        efoId (str): EFO trait identifier.
    Output:
        List[Dict[str, Any]]: List of study summaries linked to the trait.
    """
    resp = requests.get(f"{BASE_URL}/efoTraits/{efoId}/studies")
    if resp.status_code != SUCCESS_STATUS_CODE:
        return create_empty_response(resp.url, max_items_in_memory, False)  # No return_only_sig for studies
    
    items = _extract_embedded_items(resp.json(), key="studies")
    return _process_api_response(
        items=items,
        request_url=resp.url,
        max_items_in_memory=max_items_in_memory,
        return_only_sig=False,  # No return_only_sig for studies
        remove_links=remove_links,
        output_dir=output_dir,
        force_to_file=force_to_file,
        force_no_file=force_no_file,
        skip_gwas_significance=True  # Skip GWAS significance processing for studies
    )

@mcp.tool(
    name="get_trait_associations",
    description="[GWAS Catalog API] Retrieve association IDs for a specific EFO trait ID. By default, returns only genome-wide significant associations (p<5e-8). Input: efoId (str): EFO trait identifier, return_only_sig (bool, optional): If True (default), return only genome-wide significant associations, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: If successful, Dict containing: 'request_url': API request URL, 'items': List of association ID strings extracted from the '_links.self.href' field of each association (limited to max_items_in_memory), 'total_count': Total number of associations, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with 'subset_size', 'max_items_in_memory', and 'return_only_sig'. If the response format is unexpected or links are missing, returns the raw association data in the same structure. IMPORTANT: Always check 'metadata' and 'is_complete' to ensure you have all the data you need. If 'is_complete' is False, the complete dataset has been saved to 'output_file'."
)
def get_trait_associations(
    efoId: str,
    return_only_sig: bool = True,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = "/tmp",
    force_no_file: bool = False,
    remove_links: bool = True
) -> Any:
    """
    Retrieve association IDs for a specific EFO trait ID.
    By default, returns only genome-wide significant associations (p<5e-8).

    Input:
        efoId (str): EFO trait identifier.
        return_only_sig (bool, optional): If True (default), return only genome-wide significant associations.
    Output:
        List[str]: List of association ID strings linked to the trait.
    """
    resp = requests.get(f"{BASE_URL}/efoTraits/{efoId}/associations")
    if resp.status_code != SUCCESS_STATUS_CODE:
        return create_empty_response(resp.url, max_items_in_memory, return_only_sig)
    
    items = _extract_embedded_items(resp.json())
    return _process_api_response(
        items=items,
        request_url=resp.url,
        max_items_in_memory=max_items_in_memory,
        return_only_sig=return_only_sig,
        remove_links=remove_links,
        output_dir=output_dir,
        force_to_file=force_to_file,
        force_no_file=force_no_file
    )

@mcp.tool(
    name="get_region_trait_associations",
    description="[GWAS Catalog API] Retrieve associations within a genomic region for a specific EFO trait ID. By default, returns only genome-wide significant associations (p<5e-8). Input: chromosome (str): Chromosome (e.g., '1'), start (int): Base-pair lower bound, end (int): Base-pair upper bound, efo_id (str): EFO trait ID (e.g., 'EFO_0008531'), return_only_sig (bool, optional): If True (default), return only genome-wide significant associations, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: Dict containing: 'request_url': API request URL, 'items': List of associations (limited to max_items_in_memory), 'total_count': Total number of associations, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with 'subset_size', 'max_items_in_memory', and 'return_only_sig'. IMPORTANT: Always check 'metadata' and 'is_complete' to ensure you have all the data you need. If 'is_complete' is False, the complete dataset has been saved to 'output_file'."
)
def get_region_trait_associations(
    chromosome: str,
    start: int,
    end: int,
    efo_id: str,
    return_only_sig: bool = True,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = None,
    force_no_file: bool = False,
    remove_links: bool = True
) -> Any:
    """
    Retrieve associations within a genomic region for a specific EFO trait ID.
    By default, returns only genome-wide significant associations (p<5e-8).

    Input:
        chromosome (str): Chromosome (e.g., "1").
        start (int): Base-pair lower bound of the region.
        end (int): Base-pair upper bound of the region.
        efo_id (str): EFO trait identifier (e.g., "EFO_0008531").
        return_only_sig (bool, optional): If True (default), return only genome-wide significant associations.
        max_items_in_memory (int): Threshold for in-memory return. Default 5000.
        force_to_file (bool): Force file output. Default False.
        output_dir (str): Output directory for large results. Default None (auto).
        force_no_file (bool): Never write to file. Default False.
    Output:
        Dict[str, Any]: {"request_url":..., "items":..., "total_count":..., "is_complete":..., "metadata":...}
    Raises:
        ValueError: If efo_id is not a valid EFO ID format.
    """
    validate_efo_id(efo_id)
    summary_stats_base_url = "https://www.ebi.ac.uk/gwas/summary-statistics/api"
    url = f"{summary_stats_base_url}/chromosomes/{chromosome}/associations"
    params = {"bp_lower": start, "bp_upper": end, "efoTrait": efo_id}
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return create_empty_response(resp.url, max_items_in_memory, return_only_sig)
    
    items = _extract_embedded_items(resp.json())
    return _process_api_response(
        items=items,
        request_url=resp.url,
        max_items_in_memory=max_items_in_memory,
        return_only_sig=return_only_sig,
        remove_links=remove_links,
        output_dir=output_dir,
        force_to_file=force_to_file,
        force_no_file=force_no_file
    )

@mcp.tool(
    name="get_associations_from_variant",
    description="[GWAS Catalog API] Retrieve all associations for a specific variant ID using the direct SNP associations endpoint. By default, returns only genome-wide significant associations (p<5e-8). Input: variantId (str): Variant identifier (e.g., 'rs10875231'), return_only_sig (bool, optional): If True (default), return only genome-wide significant associations, max_items_in_memory (int, optional): Threshold for in-memory results (default: 5000), force_to_file (bool, optional): Force file output regardless of size, output_dir (str, optional): Directory for file output (default: /tmp), force_no_file (bool, optional): Never write to file, remove_links (bool, optional): Remove '_links' fields (default: True). Output: Dict containing: 'request_url': API request URL, 'items': List of associations (limited to max_items_in_memory), 'total_count': Total number of associations, 'is_complete': Boolean indicating if all results are included, 'metadata': Dict with 'subset_size', 'max_items_in_memory', and 'return_only_sig'. IMPORTANT: Always check 'metadata' and 'is_complete' to ensure you have all the data you need. If 'is_complete' is False, the complete dataset has been saved to 'output_file'."
)
def get_associations_from_variant(
    variantId: str = None,
    return_only_sig: bool = True,
    max_items_in_memory: int = 5000,
    force_to_file: bool = False,
    output_dir: str = None,
    force_no_file: bool = False,
    remove_links: bool = True
) -> Any:
    """
    Retrieve all associations for a specific variant ID using the direct SNP associations endpoint.
    By default, returns only genome-wide significant associations (p<5e-8).

    Input:
        variantId (str): Variant identifier (e.g., "rs10875231").
        return_only_sig (bool, optional): If True (default), return only genome-wide significant associations.
        max_items_in_memory (int, optional): Threshold for in-memory return. Default 5000.
        force_to_file (bool, optional): Force file output. Default False.
        output_dir (str, optional): Output directory for large results. Default None (auto).
        force_no_file (bool, optional): Never write to file. Default False.
        remove_links (bool, optional): If True (default), remove all '_links' fields from the output. If False, include '_links'.
    Output:
        Dict[str, Any]: {"request_url":..., "items":..., "total_count":..., "is_complete":..., "metadata":...}
    Notes:
        - This method uses the direct SNP associations endpoint which returns all associations regardless of trait.
        - For trait-specific associations, use get_associations_from_variant_and_efoid instead.
    """
    if not variantId:
        return {
            "error": "Variant ID is required. Please provide a valid variant ID (e.g., 'rs10875231').",
            "function": "get_associations_from_variant",
            "args": {"variantId": variantId}
        }

    url = f"{BASE_URL}/singleNucleotidePolymorphisms/{variantId}/associations"
    resp = requests.get(url)
    if resp.status_code != SUCCESS_STATUS_CODE:
        return create_empty_response(resp.url, max_items_in_memory, return_only_sig)
    
    items = _extract_embedded_items(resp.json())
    return _process_api_response(
        items=items,
        request_url=resp.url,
        max_items_in_memory=max_items_in_memory,
        return_only_sig=return_only_sig,
        remove_links=remove_links,
        output_dir=output_dir,
        force_to_file=force_to_file,
        force_no_file=force_no_file
    )

if __name__ == "__main__":
    mcp.run()