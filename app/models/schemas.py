from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Optional, Any

class EducationItem(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ExperienceItem(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None

class ProvenanceItem(BaseModel):
    field_path: str
    source_type: str
    source_detail: Optional[str] = None

class RawCandidate(BaseModel):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    country: Optional[str] = None

class MergedCandidate(RawCandidate):
    overall_confidence: float = 0.0
    field_confidences: Dict[str, float] = Field(default_factory=dict)
    provenance: List[ProvenanceItem] = Field(default_factory=list)

class ProjectionConfig(BaseModel):
    select_fields: Optional[List[str]] = None
    rename_fields: Optional[Dict[str, Any]] = None
    include_confidence: bool = True
    include_provenance: bool = True
    normalization: Optional[Dict[str, str]] = None
    missing_field_behavior: str = "null"  # "null", "exclude", "default", "error"
    default_values: Dict[str, Any] = Field(default_factory=dict)
