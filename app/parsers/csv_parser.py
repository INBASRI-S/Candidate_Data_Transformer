import pandas as pd
from typing import List, Dict, Any, Optional
from app.parsers.base import BaseParser
from app.models.schemas import RawCandidate, EducationItem, ExperienceItem
from app.utils.logging import logger

class CSVParser(BaseParser):
    def parse(
        self, 
        file_path: str, 
        emails: Optional[List[str]] = None, 
        names: Optional[List[str]] = None
    ) -> RawCandidate:
        logger.info(f"Parsing recruiter CSV file: {file_path}")
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                logger.warning(f"CSV file is empty: {file_path}")
                return RawCandidate()

            # Normalize column names to lowercase and strip spaces
            df.columns = [col.strip().lower() for col in df.columns]
            
            # Find the matching row
            matched_row = None
            
            # Helper to normalize values for comparison
            def clean_str(v):
                return str(v).strip().lower() if pd.notna(v) else ""

            # Check matching by email (highest precision match)
            if emails:
                emails_clean = {e.strip().lower() for e in emails if e}
                email_cols = ["email", "emails", "email_address", "email address"]
                for col in email_cols:
                    if col in df.columns:
                        for _, r in df.iterrows():
                            # Row can have comma-separated emails
                            row_emails = self._parse_list_field(r[col])
                            row_emails_clean = {e.strip().lower() for e in row_emails if e}
                            if emails_clean.intersection(row_emails_clean):
                                matched_row = r.to_dict()
                                logger.info(f"Matched CSV row by email: {r[col]}")
                                break
                    if matched_row is not None:
                        break

            # Check matching by name (secondary fallback)
            if matched_row is None and names:
                names_clean = {n.strip().lower() for n in names if n}
                name_cols = ["full_name", "full name", "fullname", "name"]
                for col in name_cols:
                    if col in df.columns:
                        for _, r in df.iterrows():
                            row_name = clean_str(r[col])
                            if row_name in names_clean:
                                matched_row = r.to_dict()
                                logger.info(f"Matched CSV row by name: {r[col]}")
                                break
                    if matched_row is not None:
                        break

            # Default fallback: first row
            if matched_row is None:
                if emails or names:
                    logger.warning("Could not match any CSV row to candidate resume/name signals. Defaulting to first row.")
                row = df.iloc[0].to_dict()
            else:
                row = matched_row

            logger.debug(f"CSV row parsed: {row}")
            return self._map_row_to_candidate(row)
        except Exception as e:
            logger.error(f"Error parsing CSV file {file_path}: {e}")
            raise

    def _map_row_to_candidate(self, row: Dict[str, Any]) -> RawCandidate:
        # Resolve fields based on standard column headers
        full_name = self._find_value(row, ["full_name", "full name", "fullname", "name"])
        first_name = self._find_value(row, ["first_name", "first name", "firstname"])
        last_name = self._find_value(row, ["last_name", "last name", "lastname"])
        
        # Email & Phone list extraction (could be comma separated or single)
        emails = self._parse_list_field(self._find_value(row, ["email", "emails", "email_address", "email address"]))
        phones = self._parse_list_field(self._find_value(row, ["phone", "phones", "phone_number", "phone number", "telephone", "mobile"]))
        
        # Skills list
        skills = self._parse_list_field(self._find_value(row, ["skills", "skill", "technologies", "tags"]))
        
        country = self._find_value(row, ["country", "location", "nation"])

        # Education
        education = []
        inst = self._find_value(row, ["institution", "school", "university", "education_institution", "education institution"])
        deg = self._find_value(row, ["degree", "education_degree", "education degree"])
        field = self._find_value(row, ["field_of_study", "field of study", "major", "specialization"])
        edu_start = self._find_value(row, ["education_start_date", "education start date", "education start", "edu_start", "school_start"])
        edu_end = self._find_value(row, ["education_end_date", "education end date", "education end", "edu_end", "school_end"])
        
        if inst or deg or field:
            education.append(EducationItem(
                institution=str(inst) if inst is not None else None,
                degree=str(deg) if deg is not None else None,
                field_of_study=str(field) if field is not None else None,
                start_date=str(edu_start) if edu_start is not None else None,
                end_date=str(edu_end) if edu_end is not None else None
            ))

        # Experience
        experience = []
        comp = self._find_value(row, ["company", "employer", "experience_company", "experience company"])
        title = self._find_value(row, ["title", "job_title", "job title", "role", "experience_title", "experience title"])
        exp_start = self._find_value(row, ["experience_start_date", "experience start date", "experience start", "exp_start", "work_start"])
        exp_end = self._find_value(row, ["experience_end_date", "experience end date", "experience end", "exp_end", "work_end"])
        desc = self._find_value(row, ["description", "summary", "experience_description", "job description"])

        if comp or title or desc:
            experience.append(ExperienceItem(
                company=str(comp) if comp is not None else None,
                title=str(title) if title is not None else None,
                start_date=str(exp_start) if exp_start is not None else None,
                end_date=str(exp_end) if exp_end is not None else None,
                description=str(desc) if desc is not None else None
            ))

        return RawCandidate(
            full_name=str(full_name) if full_name is not None else None,
            first_name=str(first_name) if first_name is not None else None,
            last_name=str(last_name) if last_name is not None else None,
            emails=emails,
            phones=phones,
            skills=skills,
            education=education,
            experience=experience,
            country=str(country) if country is not None else None
        )

    def _find_value(self, row: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        for key in keys:
            if key in row:
                val = row[key]
                if pd.isna(val):
                    return None
                return val
        return None

    def _parse_list_field(self, val: Optional[Any]) -> List[str]:
        if val is None:
            return []
        if isinstance(val, (int, float)):
            if isinstance(val, float) and val.is_integer():
                return [str(int(val))]
            return [str(val)]
        val_str = str(val).strip()
        if not val_str:
            return []
        # Support comma, semicolon, or vertical bar separation
        delimiters = [',', ';', '|']
        for delim in delimiters:
            if delim in val_str:
                return [item.strip() for item in val_str.split(delim) if item.strip()]
        return [val_str]

    def parse_all(self, file_path: str) -> List[RawCandidate]:
        logger.info(f"Parsing all recruiter CSV rows: {file_path}")
        candidates = []
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                logger.warning(f"CSV file is empty: {file_path}")
                return []
            df.columns = [col.strip().lower() for col in df.columns]
            for _, r in df.iterrows():
                row = r.to_dict()
                candidates.append(self._map_row_to_candidate(row))
            return candidates
        except Exception as e:
            logger.error(f"Error parsing all CSV rows: {e}")
            raise
