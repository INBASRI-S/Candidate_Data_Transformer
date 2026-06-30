from typing import Dict, Any, Optional
from app.models.schemas import MergedCandidate, ProjectionConfig
from app.utils.logging import logger

# Global alias fallback mapping dictionary for custom schema fields
ALIAS_FALLBACKS = {
    "candidate_name": "full_name",
    "name": "full_name",
    "contact_emails": "emails",
    "email": "emails",
    "contact_numbers": "phones",
    "contact_number": "phones",
    "phone": "phones",
    "mobile": "phones",
    "technical_skills": "skills",
    "data_provenance": "provenance",
    "confidence_rating": "overall_confidence",
    "confidence": "overall_confidence"
}

def project_candidate(
    candidate: MergedCandidate, 
    config: Optional[ProjectionConfig] = None
) -> Dict[str, Any]:
    """
    Applies the projection configuration to the candidate profile.
    It filters/renames fields, handles confidence scores inclusion/exclusion,
    applies runtime field normalizations, and configures missing field behavior.
    Returns the projected dictionary.
    """
    logger.info("Applying projection layer on candidate profile...")
    
    # 1. Convert candidate to dictionary (using deep copy via model_dump)
    data = candidate.model_dump()
    
    # Use default config if none provided
    if not config:
        config = ProjectionConfig()
        
    logger.debug(f"Applying projection config: {config.model_dump()}")

    # 2. Separate confidence and provenance data from core dictionary
    confidence_data = {
        "overall_confidence": data.pop("overall_confidence", 0.0),
        "field_confidences": data.pop("field_confidences", {}),
        "provenance": data.pop("provenance", [])
    }

    # 3. Handle per-field runtime normalization
    if config.normalization:
        for field, norm_type in config.normalization.items():
            if field in data and data[field]:
                norm_type_lower = norm_type.lower()
                if field == "skills":
                    if norm_type_lower == "lowercase":
                        data[field] = [s.lower() for s in data[field]]
                    elif norm_type_lower == "uppercase":
                        data[field] = [s.upper() for s in data[field]]
                elif field == "emails":
                    if norm_type_lower == "uppercase":
                        data[field] = [e.upper() for e in data[field]]
                elif field == "phones":
                    # Can be extended if needed, currently E.164 by default
                    pass

    # 4. Construct the fully renamed/remapped dictionary containing all available candidate fields
    mapped_data = {}
    
    # Add canonical keys (with original names) to mapped_data pool
    for canonical_key in list(data.keys()) + ["overall_confidence", "field_confidences", "provenance"]:
        if canonical_key in data:
            val = data[canonical_key]
        elif canonical_key == "overall_confidence":
            val = confidence_data["overall_confidence"]
        elif canonical_key == "field_confidences":
            val = confidence_data["field_confidences"]
        elif canonical_key == "provenance":
            val = confidence_data["provenance"]
        else:
            val = None
        mapped_data[canonical_key] = val
        
    # Apply rename_fields mapping configuration
    if config.rename_fields:
        new_mapped_data = {}
        renamed_canonical_keys = set()
        
        # Build mappings of (source_canonical, target_name)
        # Direct style: {"full_name": "candidate_name"}
        # "from" style: {"candidate_name": {"from": "full_name"}}
        mappings = []
        for k, v in config.rename_fields.items():
            if isinstance(v, dict) and "from" in v:
                mappings.append((v["from"], k))
            else:
                mappings.append((k, v))
                
        # Apply renaming maps
        for source, target in mappings:
            if source in mapped_data:
                new_mapped_data[target] = mapped_data[source]
                renamed_canonical_keys.add(source)
                
        # Copy remaining unrenamed canonical fields
        for k, v in mapped_data.items():
            if k not in renamed_canonical_keys:
                new_mapped_data[k] = v
                
        mapped_data = new_mapped_data

    # 5. Determine the final output keys list
    if config.select_fields:
        # Include all requested fields (even if they are missing/renamed and not yet in mapped_data)
        final_keys = config.select_fields
    else:
        # If select_fields is not specified, include all mapped fields
        final_keys = list(mapped_data.keys())
        # Apply include_confidence and include_provenance toggles on default standard schema
        if not config.include_confidence:
            final_keys = [k for k in final_keys if k not in ["overall_confidence", "field_confidences"]]
        if not config.include_provenance:
            final_keys = [k for k in final_keys if k != "provenance"]

    # 6. Construct Final Projected Output Dictionary with missing field handling
    projected_data = {}
    for key in final_keys:
        val = mapped_data.get(key)

        # Apply automatic fallback mapping if field value is missing and matches a known alias
        if val is None and key in ALIAS_FALLBACKS:
            fallback_key = ALIAS_FALLBACKS[key]
            val = mapped_data.get(fallback_key)

        # Check if value is missing/empty
        is_missing = False
        if val is None:
            is_missing = True
        elif isinstance(val, list) and len(val) == 0:
            is_missing = True
        elif isinstance(val, str) and len(val.strip()) == 0:
            is_missing = True

        if is_missing:
            behavior = config.missing_field_behavior.lower()
            if behavior in ["exclude", "omit"]:
                # Exclude key from output completely
                continue
            elif behavior == "error":
                # Raise exception to be caught in main.py transform route
                raise ValueError(f"Required output field '{key}' is missing.")
            elif behavior == "default":
                # Use default value if specified, else None/null
                default_val = config.default_values.get(key)
                projected_data[key] = default_val if default_val is not None else None
            else:  # "null"
                projected_data[key] = None
        else:
            projected_data[key] = val

    return projected_data
