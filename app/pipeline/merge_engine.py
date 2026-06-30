from typing import List, Dict
from app.models.schemas import RawCandidate, EducationItem, ExperienceItem, ProvenanceItem
from app.pipeline.normalization import (
    normalize_email,
    normalize_phone,
    normalize_skill,
    normalize_date,
    normalize_country
)
from app.utils.logging import logger

def merge_candidates(candidates_with_source: List[tuple[RawCandidate, str, str]]) -> RawCandidate:
    """
    Merges candidate data from multiple sources.
    Each item in the input list is a tuple: (RawCandidate, source_type, source_detail).
    Returns a unified RawCandidate.
    """
    logger.info("Merging candidate profiles from all sources...")
    
    emails_set = set()
    phones_set = set()
    skills_set = set()
    
    # Store education and experience records keyed by unique signatures to merge them
    education_map: Dict[str, EducationItem] = {}
    experience_map: Dict[str, ExperienceItem] = {}
    
    # Track the sources that contributed to list fields to build provenance later
    for candidate, source_type, source_detail in candidates_with_source:
        logger.debug(f"Processing candidate source: {source_type} ({source_detail})")
        
        # Merge Emails
        for email in candidate.emails:
            norm_email = normalize_email(email)
            if norm_email:
                emails_set.add(norm_email)
                
        # Merge Phones
        for phone in candidate.phones:
            norm_phone = normalize_phone(phone)
            if norm_phone:
                phones_set.add(norm_phone)
                
        # Merge Skills
        for skill in candidate.skills:
            norm_skill = normalize_skill(skill)
            if norm_skill:
                skills_set.add(norm_skill)
                
        # Merge Education
        for edu in candidate.education:
            school = (edu.institution or "").strip()
            degree = (edu.degree or "").strip()
            if not school:
                continue
                
            # Define signature for deduplication
            signature = f"{school.lower()}|{degree.lower()}"
            
            norm_start = normalize_date(edu.start_date) if edu.start_date else None
            norm_end = normalize_date(edu.end_date) if edu.end_date else None
            
            if signature not in education_map:
                education_map[signature] = EducationItem(
                    institution=school,
                    degree=degree if degree else None,
                    field_of_study=edu.field_of_study.strip() if edu.field_of_study else None,
                    start_date=norm_start,
                    end_date=norm_end
                )
            else:
                # Merge fields if missing in the existing record
                existing = education_map[signature]
                if not existing.field_of_study and edu.field_of_study:
                    existing.field_of_study = edu.field_of_study.strip()
                if not existing.start_date and norm_start:
                    existing.start_date = norm_start
                if not existing.end_date and norm_end:
                    existing.end_date = norm_end

        # Merge Experience
        for exp in candidate.experience:
            company = (exp.company or "").strip()
            title = (exp.title or "").strip()
            if not company:
                continue
                
            signature = f"{company.lower()}|{title.lower()}"
            
            norm_start = normalize_date(exp.start_date) if exp.start_date else None
            norm_end = normalize_date(exp.end_date) if exp.end_date else None
            
            if signature not in experience_map:
                experience_map[signature] = ExperienceItem(
                    company=company,
                    title=title if title else None,
                    start_date=norm_start,
                    end_date=norm_end,
                    description=exp.description.strip() if exp.description else None
                )
            else:
                existing = experience_map[signature]
                if not existing.start_date and norm_start:
                    existing.start_date = norm_start
                if not existing.end_date and norm_end:
                    existing.end_date = norm_end
                # Combine descriptions if they are different
                if exp.description:
                    desc_strip = exp.description.strip()
                    if not existing.description:
                        existing.description = desc_strip
                    elif desc_strip not in existing.description:
                        existing.description += f" | {desc_strip}"
                        
    merged_emails = sorted(list(emails_set))
    merged_phones = sorted(list(phones_set))
    merged_skills = sorted(list(skills_set))
    merged_education = list(education_map.values())
    merged_experience = list(experience_map.values())
    
    logger.info(f"Merge summary: {len(merged_emails)} emails, {len(merged_phones)} phones, {len(merged_skills)} skills, {len(merged_education)} education records, {len(merged_experience)} experience records.")

    return RawCandidate(
        emails=merged_emails,
        phones=merged_phones,
        skills=merged_skills,
        education=merged_education,
        experience=merged_experience
    )
