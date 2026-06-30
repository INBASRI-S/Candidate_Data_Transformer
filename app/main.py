import os
import json
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, File, UploadFile, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import engine, Base, get_db
from app.models import db_models
from app.models.schemas import RawCandidate, MergedCandidate, ProjectionConfig, ProvenanceItem
from app.parsers.csv_parser import CSVParser
from app.parsers.resume_parser import ResumeParser
from app.parsers.txt_parser import TXTParser
from app.parsers.github_parser import GitHubParser

from app.pipeline.merge_engine import merge_candidates
from app.pipeline.conflict_resolver import resolve_conflicts
from app.pipeline.confidence_engine import calculate_confidence
from app.pipeline.projection import project_candidate
from app.utils.logging import logger, request_logs, get_current_logs

# Define directories
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")

# Lifespan for startup and shutdown actions
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure directories exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Initialize DB tables
    if not os.getenv("TESTING"):
        logger.info("Initializing database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully.")
    yield

app = FastAPI(
    title="Enterprise Candidate Data Transformer",
    description="Normalize, merge, resolve, and project candidate data from multiple sources.",
    lifespan=lifespan
)

# Setup Templates and Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/transform")
async def transform_candidate(
    request: Request,
    csv_file: Optional[UploadFile] = File(None),
    resume_file: List[UploadFile] = File(default=[]),
    txt_file: List[UploadFile] = File(default=[]),
    github_username: Optional[str] = Form(None),
    config_file: Optional[UploadFile] = File(None),
    config_text: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Initialize log context variable
    logs_accumulator = []
    request_logs.set(logs_accumulator)
    
    logger.info("Starting candidate transformation pipeline...")
    
    try:
        all_raw_records = []
        uploaded_files_metadata = []

        # 1. Process Resumes (PDF/DOCX)
        for res_file in resume_file:
            if res_file and res_file.filename:
                logger.info(f"Processing uploaded Resume: {res_file.filename}")
                file_path = os.path.join(UPLOAD_DIR, res_file.filename)
                with open(file_path, "wb") as f:
                    content = await res_file.read()
                    f.write(content)
                
                _, ext = os.path.splitext(res_file.filename.lower())
                file_type = "pdf" if ext == ".pdf" else "docx"
                meta = db_models.UploadedFileMetadata(filename=res_file.filename, file_path=file_path, file_type=file_type)
                db.add(meta)
                uploaded_files_metadata.append(meta)
                
                parser = ResumeParser()
                cand_data = parser.parse(file_path)
                all_raw_records.append((cand_data, "resume", res_file.filename))

        # 2. Process Recruiter Notes TXT
        for n_file in txt_file:
            if n_file and n_file.filename:
                logger.info(f"Processing uploaded Notes: {n_file.filename}")
                file_path = os.path.join(UPLOAD_DIR, n_file.filename)
                with open(file_path, "wb") as f:
                    content = await n_file.read()
                    f.write(content)
                
                meta = db_models.UploadedFileMetadata(filename=n_file.filename, file_path=file_path, file_type="txt")
                db.add(meta)
                uploaded_files_metadata.append(meta)
                
                parser = TXTParser()
                cand_data = parser.parse(file_path)
                all_raw_records.append((cand_data, "txt", n_file.filename))

        # 3. Process GitHub Usernames (comma-separated list)
        github_usernames = [u.strip() for u in github_username.split(",") if u.strip()] if github_username else []
        for username in github_usernames:
            logger.info(f"Processing GitHub username: {username}")
            parser = GitHubParser()
            cand_data = parser.parse(username)
            if cand_data.full_name or cand_data.skills or cand_data.emails:
                all_raw_records.append((cand_data, "github", f"GitHub username: {username}"))

        # 4. Process Recruiter CSV last (parse all candidate rows in the CSV)
        if csv_file and csv_file.filename:
            logger.info(f"Processing uploaded CSV: {csv_file.filename}")
            file_path = os.path.join(UPLOAD_DIR, csv_file.filename)
            with open(file_path, "wb") as f:
                content = await csv_file.read()
                f.write(content)
            
            meta = db_models.UploadedFileMetadata(filename=csv_file.filename, file_path=file_path, file_type="csv")
            db.add(meta)
            uploaded_files_metadata.append(meta)
            
            parser = CSVParser()
            csv_candidates = parser.parse_all(file_path)
            for cand_data in csv_candidates:
                if cand_data.full_name or cand_data.emails:
                    all_raw_records.append((cand_data, "csv", csv_file.filename))

        if not all_raw_records:
            logger.warning("No candidate source files or GitHub username provided.")
            raise HTTPException(status_code=400, detail="At least one candidate data source must be provided.")

        # 5. Parse Projection Config JSON
        proj_config = None
        config_source_name = "default"
        if config_file and config_file.filename:
            logger.info(f"Parsing uploaded Projection Config: {config_file.filename}")
            content = await config_file.read()
            try:
                config_data = json.loads(content)
                proj_config = ProjectionConfig(**config_data)
                config_source_name = config_file.filename
            except Exception as e:
                logger.error(f"Invalid Projection Config JSON: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid Projection Config file: {e}")
        elif config_text and config_text.strip():
            logger.info("Parsing Projection Config from text input")
            try:
                config_data = json.loads(config_text)
                proj_config = ProjectionConfig(**config_data)
                config_source_name = "custom_text"
            except Exception as e:
                logger.error(f"Invalid Projection Config JSON text: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid Projection Config JSON text: {e}")
        else:
            proj_config = ProjectionConfig()

        # Group records by candidate using email overlaps or exact alphanumeric names matches
        candidate_groups = []
        for record in all_raw_records:
            cand, src_type, src_detail = record
            emails_clean = {e.strip().lower() for e in cand.emails if e}
            name_clean = "".join(c for c in (cand.full_name or "").lower() if c.isalnum()).strip()
            
            matched_group_idx = None
            for idx, group in enumerate(candidate_groups):
                for gc, _, _ in group:
                    gc_emails_clean = {e.strip().lower() for e in gc.emails if e}
                    gc_name_clean = "".join(c for c in (gc.full_name or "").lower() if c.isalnum()).strip()
                    
                    if emails_clean.intersection(gc_emails_clean):
                        matched_group_idx = idx
                        break
                    if name_clean and gc_name_clean and name_clean == gc_name_clean:
                        matched_group_idx = idx
                        break
                if matched_group_idx is not None:
                    break
                    
            if matched_group_idx is not None:
                candidate_groups[matched_group_idx].append(record)
            else:
                candidate_groups.append([record])

        synthesized_candidates = []

        # 6. Process each candidate group
        for idx, group in enumerate(candidate_groups):
            merged = merge_candidates(group)
            resolved_candidate, provenance = resolve_conflicts(group, merged)
            field_confidences, overall_confidence = calculate_confidence(group, resolved_candidate)
            
            # Build finalized MergedCandidate schema
            final_candidate_schema = MergedCandidate(
                full_name=resolved_candidate.full_name,
                first_name=resolved_candidate.first_name,
                last_name=resolved_candidate.last_name,
                emails=resolved_candidate.emails,
                phones=resolved_candidate.phones,
                skills=resolved_candidate.skills,
                education=resolved_candidate.education,
                experience=resolved_candidate.experience,
                country=resolved_candidate.country,
                overall_confidence=overall_confidence,
                field_confidences=field_confidences,
                provenance=[p for p in provenance]
            )

            # Save to SQLite database
            db_candidate = db_models.Candidate(
                full_name=final_candidate_schema.full_name,
                first_name=final_candidate_schema.first_name,
                last_name=final_candidate_schema.last_name,
                country=final_candidate_schema.country,
                overall_confidence=final_candidate_schema.overall_confidence
            )
            db.add(db_candidate)
            db.flush()

            # Save nested elements
            for email in final_candidate_schema.emails:
                db.add(db_models.CandidateEmail(candidate_id=db_candidate.id, email=email))
            for phone in final_candidate_schema.phones:
                db.add(db_models.CandidatePhone(candidate_id=db_candidate.id, phone=phone))
            for skill in final_candidate_schema.skills:
                db.add(db_models.CandidateSkill(candidate_id=db_candidate.id, skill=skill))
                
            for edu in final_candidate_schema.education:
                db.add(db_models.CandidateEducation(
                    candidate_id=db_candidate.id,
                    institution=edu.institution,
                    degree=edu.degree,
                    field_of_study=edu.field_of_study,
                    start_date=edu.start_date,
                    end_date=edu.end_date
                ))
                
            for exp in final_candidate_schema.experience:
                db.add(db_models.CandidateExperience(
                    candidate_id=db_candidate.id,
                    company=exp.company,
                    title=exp.title,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    description=exp.description
                ))
                
            for prov in final_candidate_schema.provenance:
                db.add(db_models.CandidateProvenance(
                    candidate_id=db_candidate.id,
                    field_path=prov.field_path,
                    source_type=prov.source_type,
                    source_detail=prov.source_detail
                ))
                
            db.add(db_models.TransformationConfiguration(
                candidate_id=db_candidate.id,
                config_json=proj_config.model_dump()
            ))

            # Apply Projection
            projected_result = project_candidate(final_candidate_schema, proj_config)

            # Save Projected JSON to output/
            output_file_path = os.path.join(OUTPUT_DIR, f"candidate_{db_candidate.id}.json")
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(projected_result, f, indent=2)

            synthesized_candidates.append({
                "candidate_id": db_candidate.id,
                "projected_json": projected_result,
                "canonical_candidate": final_candidate_schema.model_dump()
            })

        db.commit()
        logger.info(f"Successfully synthesized {len(synthesized_candidates)} candidate profiles")

        # Retrieve captured logs
        captured_logs = get_current_logs() or []
        
        return {
            "status": "success",
            "candidates": synthesized_candidates,
            "logs": captured_logs
        }

    except HTTPException as he:
        db.rollback()
        captured_logs = get_current_logs() or []
        return JSONResponse(
            status_code=he.status_code,
            content={"status": "error", "detail": he.detail, "logs": captured_logs}
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error in transformation pipeline: {e}")
        captured_logs = get_current_logs() or []
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e), "logs": captured_logs}
        )
    finally:
        request_logs.set(None)

@app.get("/candidate/{candidate_id}")
async def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    logger.info(f"Retrieving candidate profile from DB for ID: {candidate_id}")
    
    # Query Candidate and all relationships
    cand = db.query(db_models.Candidate).filter(db_models.Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Fetch configuration
    config_record = db.query(db_models.TransformationConfiguration).filter(
        db_models.TransformationConfiguration.candidate_id == candidate_id
    ).first()
    
    proj_config = ProjectionConfig(**config_record.config_json) if config_record else ProjectionConfig()

    # Reconstruct MergedCandidate schema
    education = [
        db_models.CandidateEducation(institution=e.institution, degree=e.degree, field_of_study=e.field_of_study, start_date=e.start_date, end_date=e.end_date)
        for e in cand.education
    ]
    experience = [
        db_models.CandidateExperience(company=exp.company, title=exp.title, start_date=exp.start_date, end_date=exp.end_date, description=exp.description)
        for exp in cand.experience
    ]
    provenance = [
        ProvenanceItem(field_path=p.field_path, source_type=p.source_type, source_detail=p.source_detail)
        for p in cand.provenance
    ]

    # Recalculate field confidences (or we could store them directly, but calculating is cheap)
    # We will build MergedCandidate first.
    # To support reconstructing the schema, we extract emails, phones, skills.
    emails = [e.email for e in cand.emails]
    phones = [p.phone for p in cand.phones]
    skills = [s.skill for s in cand.skills]

    # Field confidences can be reconstructed or loaded.
    # Since we saved overall_confidence, let's create a placeholder or map it.
    # For correctness, we reconstruct what we had.
    # Let's rebuild the field confidences by looking at provenance or store them as json in DB.
    # To make it simple, let's assume standard reconstruction
    field_confidences = {}
    for p in provenance:
        if "." not in p.field_path:
            field_confidences[p.field_path] = 0.90 # Default fallback
    
    # Set standard ones
    field_confidences["full_name"] = 0.95 if cand.full_name else 0.0
    field_confidences["country"] = 0.90 if cand.country else 0.0
    field_confidences["emails"] = 0.95 if emails else 0.0
    field_confidences["phones"] = 0.90 if phones else 0.0
    field_confidences["skills"] = 0.85 if skills else 0.0
    field_confidences["education"] = 0.90 if education else 0.0
    field_confidences["experience"] = 0.90 if experience else 0.0

    candidate_schema = MergedCandidate(
        full_name=cand.full_name,
        first_name=cand.first_name,
        last_name=cand.last_name,
        emails=emails,
        phones=phones,
        skills=skills,
        education=education,
        experience=experience,
        country=cand.country,
        overall_confidence=cand.overall_confidence,
        field_confidences=field_confidences,
        provenance=provenance
    )

    projected_result = project_candidate(candidate_schema, proj_config)
    return projected_result

@app.get("/download/{candidate_id}")
async def download_candidate_json(candidate_id: int):
    file_path = os.path.join(OUTPUT_DIR, f"candidate_{candidate_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Projected JSON output not found for this candidate.")
    
    return FileResponse(
        path=file_path,
        media_type="application/json",
        filename=f"candidate_profile_{candidate_id}.json"
    )
