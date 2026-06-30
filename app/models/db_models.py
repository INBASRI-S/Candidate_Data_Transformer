from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database.connection import Base

class UploadedFileMetadata(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # csv, json, pdf, docx, txt
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    country = Column(String, nullable=True)
    overall_confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    emails = relationship("CandidateEmail", back_populates="candidate", cascade="all, delete-orphan")
    phones = relationship("CandidatePhone", back_populates="candidate", cascade="all, delete-orphan")
    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan")
    education = relationship("CandidateEducation", back_populates="candidate", cascade="all, delete-orphan")
    experience = relationship("CandidateExperience", back_populates="candidate", cascade="all, delete-orphan")
    provenance = relationship("CandidateProvenance", back_populates="candidate", cascade="all, delete-orphan")
    configurations = relationship("TransformationConfiguration", back_populates="candidate", cascade="all, delete-orphan")

class CandidateEmail(Base):
    __tablename__ = "candidate_emails"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)

    candidate = relationship("Candidate", back_populates="emails")

class CandidatePhone(Base):
    __tablename__ = "candidate_phones"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    phone = Column(String, nullable=False)

    candidate = relationship("Candidate", back_populates="phones")

class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    skill = Column(String, nullable=False)

    candidate = relationship("Candidate", back_populates="skills")

class CandidateEducation(Base):
    __tablename__ = "candidate_education"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    institution = Column(String, nullable=True)
    degree = Column(String, nullable=True)
    field_of_study = Column(String, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)

    candidate = relationship("Candidate", back_populates="education")

class CandidateExperience(Base):
    __tablename__ = "candidate_experience"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    company = Column(String, nullable=True)
    title = Column(String, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    candidate = relationship("Candidate", back_populates="experience")

class CandidateProvenance(Base):
    __tablename__ = "candidate_provenance"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    field_path = Column(String, nullable=False)  # e.g., "full_name", "emails", "skills"
    source_type = Column(String, nullable=False)  # e.g., "github", "resume", "ats", "csv", "txt"
    source_detail = Column(String, nullable=True)  # e.g., file path, github URL, user name

    candidate = relationship("Candidate", back_populates="provenance")

class TransformationConfiguration(Base):
    __tablename__ = "transformation_configurations"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    config_json = Column(JSON, nullable=False)

    candidate = relationship("Candidate", back_populates="configurations")
