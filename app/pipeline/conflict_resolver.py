import re
from typing import List, Dict, Tuple, Optional, Any
from app.models.schemas import RawCandidate, ProvenanceItem
from app.pipeline.normalization import normalize_country
from app.utils.logging import logger

# Source priorities (highest to lowest)
SOURCE_PRIORITIES = ["resume", "github", "csv", "txt"]

def resolve_conflicts(
    candidates_with_source: List[Tuple[RawCandidate, str, str]], 
    merged_candidate: RawCandidate
) -> Tuple[RawCandidate, List[ProvenanceItem]]:
    """
    Resolves conflicts for single-value fields (full_name, first_name, last_name, country)
    based on the source priority order: GitHub > Resume > Recruiter CSV > TXT Notes.
    Also returns the provenance tracking where each field value originated.
    """
    logger.info("Resolving single-value conflicts and tracking provenance...")
    
    # Organize candidates by source_type for easy access
    source_map: Dict[str, Tuple[RawCandidate, str]] = {}
    for candidate, s_type, s_detail in candidates_with_source:
        source_map[s_type.lower()] = (candidate, s_detail)

    provenance_list: List[ProvenanceItem] = []
    
    # 1. Resolve full_name
    resolved_full_name, name_source_type, name_source_detail = resolve_field(source_map, "full_name")
    if resolved_full_name:
        merged_candidate.full_name = resolved_full_name
        provenance_list.append(ProvenanceItem(
            field_path="full_name",
            source_type=name_source_type,
            source_detail=name_source_detail
        ))
        
        # Split first and last names based on resolved full name
        parts = resolved_full_name.split(None, 1)
        merged_candidate.first_name = parts[0] if len(parts) > 0 else None
        merged_candidate.last_name = parts[1] if len(parts) > 1 else None
        
        if merged_candidate.first_name:
            provenance_list.append(ProvenanceItem(
                field_path="first_name",
                source_type=name_source_type,
                source_detail=name_source_detail
            ))
        if merged_candidate.last_name:
            provenance_list.append(ProvenanceItem(
                field_path="last_name",
                source_type=name_source_type,
                source_detail=name_source_detail
            ))
    else:
        # If no full_name is found, try resolving first_name and last_name independently
        resolved_first_name, f_source_type, f_source_detail = resolve_field(source_map, "first_name")
        resolved_last_name, l_source_type, l_source_detail = resolve_field(source_map, "last_name")
        
        if resolved_first_name:
            merged_candidate.first_name = resolved_first_name
            provenance_list.append(ProvenanceItem(field_path="first_name", source_type=f_source_type, source_detail=f_source_detail))
        if resolved_last_name:
            merged_candidate.last_name = resolved_last_name
            provenance_list.append(ProvenanceItem(field_path="last_name", source_type=l_source_type, source_detail=l_source_detail))
            
        # Reconstruct full name
        names = [n for n in [resolved_first_name, resolved_last_name] if n]
        if names:
            merged_candidate.full_name = " ".join(names)
            provenance_list.append(ProvenanceItem(
                field_path="full_name",
                source_type=f_source_type or l_source_type or "unknown",
                source_detail=f_source_detail or l_source_detail
            ))

    # 2. Resolve country
    resolved_country, country_source_type, country_source_detail = resolve_field(source_map, "country")
    if resolved_country:
        norm_c = normalize_country(resolved_country)
        merged_candidate.country = norm_c
        provenance_list.append(ProvenanceItem(
            field_path="country",
            source_type=country_source_type,
            source_detail=country_source_detail
        ))

    # 2.5 Deduplicate phone numbers that are corrupted by scientific notation truncation
    import re
    cleaned_phones = []
    # Sort phones by priority of their sources so we check high priority sources first
    phones_with_source = []
    for phone in merged_candidate.phones:
        sources = find_sources_for_value(candidates_with_source, "phones", phone)
        # Get highest priority source index (lower is higher priority)
        best_priority = len(SOURCE_PRIORITIES)
        for s_type, _ in sources:
            if s_type.lower() in SOURCE_PRIORITIES:
                idx = SOURCE_PRIORITIES.index(s_type.lower())
                if idx < best_priority:
                    best_priority = idx
        phones_with_source.append((phone, best_priority))
        
    # Sort: highest priority first
    phones_with_source.sort(key=lambda x: x[1])
    
    for phone, priority in phones_with_source:
        # Check if this phone is a corrupted version of any phone we already accepted
        is_corrupted = False
        digits_phone = re.sub(r'[^\d]', '', phone)
        for accepted in cleaned_phones:
            digits_accepted = re.sub(r'[^\d]', '', accepted)
            if is_scientific_notation_corrupted(digits_accepted, digits_phone):
                logger.info(f"Removing scientific-notation corrupted phone: '{phone}' (duplicate of '{accepted}')")
                is_corrupted = True
                break
        if not is_corrupted:
            cleaned_phones.append(phone)
            
    merged_candidate.phones = sorted(cleaned_phones)

    # 3. Add provenance for list fields (emails, phones, skills, education, experience)
    # List fields come from multiple sources. We list the source of each distinct item.
    add_list_provenance(candidates_with_source, merged_candidate, provenance_list)

    return merged_candidate, provenance_list

def resolve_field(
    source_map: Dict[str, Tuple[RawCandidate, str]], 
    field_name: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Looks up a field in sources according to the priority order.
    Returns (resolved_value, source_type, source_detail) or (None, None, None)
    """
    for priority_source in SOURCE_PRIORITIES:
        if priority_source in source_map:
            candidate, s_detail = source_map[priority_source]
            val = getattr(candidate, field_name, None)
            if val and str(val).strip():
                logger.info(f"Resolved field '{field_name}' from priority source '{priority_source}': '{val}'")
                return str(val).strip(), priority_source, s_detail
    return None, None, None

def add_list_provenance(
    candidates_with_source: List[Tuple[RawCandidate, str, str]],
    merged: RawCandidate,
    provenance_list: List[ProvenanceItem]
):
    """
    Determines and appends the source provenance for itemized values within lists
    (emails, phones, skills, education, experience).
    """
    # Emails
    for email in merged.emails:
        sources_found = find_sources_for_value(candidates_with_source, "emails", email)
        for s_type, s_detail in sources_found:
            provenance_list.append(ProvenanceItem(
                field_path=f"emails.{email}",
                source_type=s_type,
                source_detail=s_detail
            ))

    # Phones
    for phone in merged.phones:
        sources_found = find_sources_for_value(candidates_with_source, "phones", phone)
        for s_type, s_detail in sources_found:
            provenance_list.append(ProvenanceItem(
                field_path=f"phones.{phone}",
                source_type=s_type,
                source_detail=s_detail
            ))

    # Skills
    for skill in merged.skills:
        sources_found = find_sources_for_value(candidates_with_source, "skills", skill)
        for s_type, s_detail in sources_found:
            provenance_list.append(ProvenanceItem(
                field_path=f"skills.{skill}",
                source_type=s_type,
                source_detail=s_detail
            ))

    # Education
    # Match by institution name
    for edu in merged.education:
        sources_found = find_sources_for_subobject(candidates_with_source, "education", "institution", edu.institution)
        for s_type, s_detail in sources_found:
            provenance_list.append(ProvenanceItem(
                field_path=f"education.{edu.institution}",
                source_type=s_type,
                source_detail=s_detail
            ))

    # Experience
    # Match by company name
    for exp in merged.experience:
        sources_found = find_sources_for_subobject(candidates_with_source, "experience", "company", exp.company)
        for s_type, s_detail in sources_found:
            provenance_list.append(ProvenanceItem(
                field_path=f"experience.{exp.company}",
                source_type=s_type,
                source_detail=s_detail
            ))

def find_sources_for_value(
    candidates_with_source: List[Tuple[RawCandidate, str, str]],
    field_name: str,
    target_value: str
) -> List[Tuple[str, str]]:
    sources = []
    target_lower = target_value.lower()
    for candidate, s_type, s_detail in candidates_with_source:
        list_val = getattr(candidate, field_name, [])
        # Compare lowercase elements for match
        if any(str(item).lower() == target_lower for item in list_val):
            sources.append((s_type, s_detail))
    return sources

def find_sources_for_subobject(
    candidates_with_source: List[Tuple[RawCandidate, str, str]],
    field_name: str,
    key_name: str,
    target_value: Optional[str]
) -> List[Tuple[str, str]]:
    sources = []
    if not target_value:
        return sources
    target_lower = target_value.lower().strip()
    for candidate, s_type, s_detail in candidates_with_source:
        items = getattr(candidate, field_name, [])
        for item in items:
            val = getattr(item, key_name, None)
            if val and str(val).lower().strip() == target_lower:
                sources.append((s_type, s_detail))
                break
    return sources

def is_scientific_notation_corrupted(clean_num: str, target_corrupted: str) -> bool:
    """
    Checks if target_corrupted is a scientific-notation-truncated version of clean_num.
    E.g. clean_num = "918778683374", target_corrupted = "918779000000"
    """
    if len(clean_num) != len(target_corrupted):
        return False
        
    # Count trailing zeros of the target
    zeros_match = re.search(r'0+$', target_corrupted)
    if not zeros_match:
        return False
        
    num_zeros = len(zeros_match.group(0))
    if num_zeros < 3: # Need at least 3 trailing zeros to avoid false positives
        return False
        
    sig_len = len(target_corrupted) - num_zeros
    sig_target = target_corrupted[:sig_len]
    
    try:
        # Convert the prefix of clean_num to float and round it
        val_to_round = float(clean_num) / (10 ** num_zeros)
        rounded_val = round(val_to_round)
        rounded_str = str(rounded_val)
        
        if rounded_str == sig_target:
            return True
    except Exception:
        pass
        
    return False
