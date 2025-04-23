from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class TestCase:
    """
    Represents a single test invocation.
    
    Attributes:
        name (str): Name of the server function to call
        args (Dict[str, Any]): Dictionary of arguments to pass to the function
    """
    name: str
    args: Dict[str, Any]

# Basic API test cases
basic_api_cases = [
    TestCase(name="get_study", args={"studyId": "GCST90000014"}),
    TestCase(name="get_association", args={"associationId": "14347"}),
    TestCase(name="get_variant", args={"variantId": "rs123"}),
    TestCase(name="get_trait", args={"efoId": "EFO_0000305"}),
]

# Region and variant search test cases
search_cases = [
    TestCase(name="search_variants_in_region", args={"chromosome": "1", "start": 1000000, "end": 1000100, "efo_id": "EFO_0000305"}),
    TestCase(name="get_variants_from_efo_ids", args={"efo_ids": ["EFO_0000305", "EFO_0000310"]}),
    TestCase(name="trait_variant_ranking", args={"efo_id": "EFO_0008531", "top_n": 5}),
]

# Association retrieval test cases
association_cases = [
    TestCase(name="get_study_associations", args={"studyId": "GCST90000014"}),
    TestCase(name="get_trait_studies", args={"efoId": "EFO_0000305"}),
    TestCase(name="get_trait_associations", args={"efoId": "EFO_0000305"}),
    TestCase(name="get_associations_from_variant", args={"variantId": "rs112735431"}),
    TestCase(name="get_region_trait_associations", args={"chromosome": "1", "start": 90534000, "end": 99535000, "efo_id": "EFO_0008531"}),
]

# Combine all success cases
success_cases: List[TestCase] = basic_api_cases + search_cases + association_cases

# Error test cases
error_cases: List[TestCase] = [
    # Missing required argument
    TestCase(name="error-get_study", args={}),
    # Invalid argument names
    TestCase(name="error-search_variants_in_region", args={"chrom": "1", "st": 1000, "en": 1100}),
    # Missing required variantId
    TestCase(name="error-get_associations_from_variant", args={}),
    # Unknown function
    TestCase(name="error-unknown_tool", args={}),
] 