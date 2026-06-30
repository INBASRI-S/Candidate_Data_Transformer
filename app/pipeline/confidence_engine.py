from typing import List, Dict, Tuple
from app.models.schemas import RawCandidate, MergedCandidate
from app.utils.logging import logger

def calculate_confidence(
    candidates_with_source: List[Tuple[RawCandidate, str, str]],
    merged: RawCandidate
) -> Tuple[Dict[str, float], float]:
    """
    Calculates confidence scores for important candidate fields and computes
    an overall candidate confidence score.
    Returns (field_confidences, overall_confidence_score).
    Scores are values between 0.0 and 1.0 (representing 0% to 100%).
    """
    logger.info("Calculating candidate fields confidence scores...")
    
    field_confidences: Dict[str, float] = {}

    # Helper: count how many sources had a value for a root field
    def count_source_presence(field_name: str, target_val: str) -> int:
        count = 0
        if not target_val:
            return 0
        for cand, _, _ in candidates_with_source:
            val = getattr(cand, field_name, None)
            if val and str(val).strip().lower() == target_val.lower().strip():
                count += 1
        return count

    # 1. Full Name Confidence
    if merged.full_name:
        sources_count = count_source_presence("full_name", merged.full_name)
        # Base score on presence: 1 source = 75%, 2 sources = 90%, 3+ sources = 98%
        if sources_count == 1:
            base_score = 0.75
        elif sources_count == 2:
            base_score = 0.90
        else:
            base_score = 0.98
            
        # Modifiers based on format: must contain at least 2 words
        if len(merged.full_name.split()) >= 2:
            base_score = min(1.0, base_score + 0.05)
        field_confidences["full_name"] = base_score
    else:
        field_confidences["full_name"] = 0.0

    # 2. Country Confidence
    if merged.country:
        sources_count = count_source_presence("country", merged.country)
        # Base: 1 source = 70%, 2+ = 90%
        if sources_count == 1:
            base_score = 0.70
        else:
            base_score = 0.92
        field_confidences["country"] = base_score
    else:
        field_confidences["country"] = 0.0

    # 3. Emails Confidence
    if merged.emails:
        email_scores = []
        for email in merged.emails:
            # Check how many sources contain this email
            count = 0
            for cand, _, _ in candidates_with_source:
                if any(e.lower().strip() == email.lower().strip() for e in cand.emails):
                    count += 1
            
            # Base 85% if valid, add 10% bonus if corroborated
            score = 0.85
            if count > 1:
                score = min(1.0, score + 0.10)
            email_scores.append(score)
        field_confidences["emails"] = sum(email_scores) / len(email_scores)
    else:
        field_confidences["emails"] = 0.0

    # 4. Phones Confidence
    if merged.phones:
        phone_scores = []
        for phone in merged.phones:
            count = 0
            for cand, _, _ in candidates_with_source:
                if any(p.strip() == phone.strip() for p in cand.phones):
                    count += 1
            
            # E164 phones are very reliable: base 80%, corroborated 95%
            score = 0.80
            if count > 1:
                score = min(1.0, score + 0.15)
            # Penalize slightly if the phone doesn't look normalized (doesn't start with '+')
            if not phone.startswith("+"):
                score = max(0.50, score - 0.20)
            phone_scores.append(score)
        field_confidences["phones"] = sum(phone_scores) / len(phone_scores)
    else:
        field_confidences["phones"] = 0.0

    # 5. Skills Confidence
    if merged.skills:
        skill_scores = []
        for skill in merged.skills:
            count = 0
            for cand, _, _ in candidates_with_source:
                if any(s.lower().strip() == skill.lower().strip() for s in cand.skills):
                    count += 1
            
            # If skill is verified across multiple sources, higher confidence
            score = 0.75
            if count > 1:
                score = min(1.0, score + 0.20)
            skill_scores.append(score)
        field_confidences["skills"] = sum(skill_scores) / len(skill_scores)
    else:
        field_confidences["skills"] = 0.0

    # 6. Education Confidence
    if merged.education:
        edu_scores = []
        for edu in merged.education:
            # Score based on completeness of fields
            fields_filled = sum([
                1 if edu.institution else 0,
                1 if edu.degree else 0,
                1 if edu.field_of_study else 0,
                1 if edu.start_date else 0,
                1 if edu.end_date else 0
            ])
            score = 0.50 + (fields_filled / 5.0) * 0.50  # Ranges from 50% to 100%
            edu_scores.append(score)
        field_confidences["education"] = sum(edu_scores) / len(edu_scores)
    else:
        field_confidences["education"] = 0.0

    # 7. Experience Confidence
    if merged.experience:
        exp_scores = []
        for exp in merged.experience:
            fields_filled = sum([
                1 if exp.company else 0,
                1 if exp.title else 0,
                1 if exp.start_date else 0,
                1 if exp.end_date else 0,
                1 if exp.description else 0
            ])
            score = 0.50 + (fields_filled / 5.0) * 0.50
            exp_scores.append(score)
        field_confidences["experience"] = sum(exp_scores) / len(exp_scores)
    else:
        field_confidences["experience"] = 0.0

    # Calculate Overall Candidate Confidence Score using weights:
    # Name: 25%, Emails: 15%, Phones: 15%, Skills: 15%, Experience: 15%, Education: 10%, Country: 5%
    weights = {
        "full_name": 0.25,
        "emails": 0.15,
        "phones": 0.15,
        "skills": 0.15,
        "experience": 0.15,
        "education": 0.10,
        "country": 0.05
    }
    
    overall_confidence = sum(field_confidences[field] * weight for field, weight in weights.items())
    
    logger.info(f"Calculated overall candidate confidence: {overall_confidence:.2%}")
    return field_confidences, round(overall_confidence, 4)
