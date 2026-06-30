import os
import re
import pdfplumber
import docx
import pycountry
from typing import List, Dict, Any, Optional
from app.parsers.base import BaseParser
from app.models.schemas import RawCandidate, EducationItem, ExperienceItem
from app.utils.logging import logger

# A list of common skills to scan for (case-insensitive keyword matching)
TECH_SKILLS_CATALOG = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "java": "Java",
    "c++": "C++",
    "c#": "C#",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "html": "HTML",
    "css": "CSS",
    "react": "React",
    "angular": "Angular",
    "vue": "Vue",
    "node": "Node.js",
    "node.js": "Node.js",
    "express": "Express.js",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "spring": "Spring Boot",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "sqlite": "SQLite",
    "redis": "Redis",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "git": "Git",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "Scikit-Learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "sql": "SQL",
    "graphql": "GraphQL",
    "rest": "REST API",
    "linux": "Linux",
    "agile": "Agile",
    "scrum": "Scrum",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "ci/cd": "CI/CD",
}

class ResumeParser(BaseParser):
    def parse(self, file_path: str) -> RawCandidate:
        logger.info(f"Parsing resume: {file_path}")
        _, ext = os.path.splitext(file_path.lower())
        
        try:
            if ext == ".pdf":
                text = self._extract_text_from_pdf(file_path)
            elif ext == ".docx":
                text = self._extract_text_from_docx(file_path)
            else:
                raise ValueError(f"Unsupported file format for resume: {ext}")

            if not text.strip():
                logger.warning(f"Resume text is empty: {file_path}")
                return RawCandidate()

            return self._parse_text(text)
        except Exception as e:
            logger.error(f"Error parsing resume {file_path}: {e}")
            raise

    def _extract_text_from_pdf(self, file_path: str) -> str:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text_content = page.extract_text()
                if text_content:
                    text += text_content + "\n"
        return text

    def _extract_text_from_docx(self, file_path: str) -> str:
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text

    def _parse_text(self, text: str) -> RawCandidate:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # 1. Extract Emails
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        emails = list(set([e.lower() for e in emails]))

        # 2. Extract Phone Numbers
        phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, text)
        phones = list(set([p.strip() for p in phones]))

        # 3. Extract Name (Heuristic: first few lines of text, skip headers and contact info)
        full_name = self._heuristic_extract_name(lines, emails, phones)

        # Split full name into first and last if possible
        first_name, last_name = None, None
        if full_name:
            parts = full_name.split()
            if len(parts) > 0:
                first_name = parts[0]
            if len(parts) > 1:
                last_name = " ".join(parts[1:])

        # 4. Extract Country
        country = self._heuristic_extract_country(text)

        # 5. Extract Skills
        skills = self._heuristic_extract_skills(text)

        # 6. Extract Education
        education = self._heuristic_extract_education(lines)

        # 7. Extract Experience
        experience = self._heuristic_extract_experience(lines)

        return RawCandidate(
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            emails=emails,
            phones=phones,
            skills=skills,
            education=education,
            experience=experience,
            country=country
        )

    def _heuristic_extract_name(self, lines: List[str], emails: List[str], phones: List[str]) -> Optional[str]:
        # Typically the candidate's name is on one of the first 5 lines.
        # It shouldn't contain email, phone numbers, or common section keywords.
        exclude_keywords = {"resume", "cv", "curriculum", "vitae", "portfolio", "summary", "profile", "contact"}
        org_keywords = {"college", "university", "engineering", "school", "technologies", "solutions", "corporation", "ltd", "institute"}
        
        for line in lines[:5]:
            clean_line = line.strip()
            
            # 1. Strip emails from the line
            clean_line = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '', clean_line)
            # 2. Strip URLs from the line
            clean_line = re.sub(r'https?://\S+', '', clean_line)
            # 3. Strip common delimiters
            clean_line = re.sub(r'[|/:\-,]', ' ', clean_line)
            # 4. Collapse extra whitespaces
            clean_line = " ".join(clean_line.split())
            
            # Skip if it is too short or too long
            if not (3 <= len(clean_line) <= 40):
                continue
            # Skip if it contains numbers
            if any(char.isdigit() for char in clean_line):
                continue
            # Skip if it's just section titles
            if clean_line.lower() in exclude_keywords:
                continue
            # Skip if it contains common organization/college keywords
            if any(org_kw in clean_line.lower() for org_kw in org_keywords):
                continue
            
            # Check if it consists mostly of alphabetic words
            words = clean_line.split()
            if 1 <= len(words) <= 4 and all(w.replace(".", "").isalpha() for w in words):
                return clean_line
        return None

    def _heuristic_extract_country(self, text: str) -> Optional[str]:
        # Perform quick checks against pycountry database
        # To avoid false positives on common words (like "Jobs", "Of"), we search for countries with long names
        # or do exact matches on country names.
        text_lower = text.lower()
        for country in pycountry.countries:
            c_name = country.name.lower()
            # Avoid tiny names or names that might conflict (e.g. "US" or "IN" can be acronyms)
            if len(c_name) > 3 and c_name in text_lower:
                # Basic boundary check
                pattern = rf'\b{re.escape(c_name)}\b'
                if re.search(pattern, text_lower):
                    return country.name
        
        # Check standard abbreviations
        if re.search(r'\bUSA\b', text):
            return "United States"
        if re.search(r'\bUK\b', text):
            return "United Kingdom"
        
        return None

    def _heuristic_extract_skills(self, text: str) -> List[str]:
        matched_skills = set()
        text_lower = text.lower()
        for key, canonical_name in TECH_SKILLS_CATALOG.items():
            pattern = rf'\b{re.escape(key)}\b'
            if re.search(pattern, text_lower):
                matched_skills.add(canonical_name)
        return sorted(list(matched_skills))

    def _heuristic_extract_education(self, lines: List[str]) -> List[EducationItem]:
        education_items = []
        in_education_section = False
        edu_lines = []
        
        # Section keywords
        edu_section_triggers = {"education", "academic", "studies", "qualification"}
        other_section_triggers = {"experience", "employment", "work", "history", "skills", "projects", "certifications", "interests"}

        for line in lines:
            line_lower = line.lower().strip()
            
            # Detect section boundary using word boundary checks
            if any(re.search(rf'\b{re.escape(trigger)}\b', line_lower) for trigger in edu_section_triggers):
                in_education_section = True
                continue
            elif in_education_section and any(re.search(rf'\b{re.escape(trigger)}\b', line_lower) for trigger in other_section_triggers):
                in_education_section = False
                break
            
            if in_education_section:
                edu_lines.append(line)

        # Parse lines within the education section
        # Heuristics: Look for university/college name + degree details + date
        current_inst = None
        current_deg = None
        current_field = None
        current_start = None
        current_end = None

        date_pattern = r'\b(19\d{2}|20\d{2})\b'

        for eline in edu_lines:
            eline_lower = eline.lower()
            
            # School detection
            if any(keyword in eline_lower for keyword in ["university", "college", "institute", "school", "academy"]):
                # If we already have a school, save previous one and start a new one
                if current_inst:
                    education_items.append(EducationItem(
                        institution=current_inst,
                        degree=current_deg,
                        field_of_study=current_field,
                        start_date=current_start,
                        end_date=current_end
                    ))
                    current_deg, current_field, current_start, current_end = None, None, None, None
                
                current_inst = eline.strip()
            
            # Degree detection
            if any(keyword in eline_lower for keyword in ["bachelor", "master", "doctor", "phd", "b.s", "m.s", "b.a", "m.a", "btech", "mtech", "b.tech", "m.tech", "diploma", "degree"]):
                current_deg = eline.strip()
                # Try to extract major/field
                parts = re.split(r'\bin\b', eline, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) > 1:
                    current_field = parts[1].strip()

            # Date extraction
            dates = re.findall(date_pattern, eline)
            if dates:
                if len(dates) >= 2:
                    current_start, current_end = dates[0], dates[1]
                else:
                    current_end = dates[0]
                    if "present" in eline_lower:
                        current_start = dates[0]
                        current_end = "Present"

        # Append last item
        if current_inst:
            education_items.append(EducationItem(
                institution=current_inst,
                degree=current_deg,
                field_of_study=current_field,
                start_date=current_start,
                end_date=current_end
            ))

        return education_items

    def _heuristic_extract_experience(self, lines: List[str]) -> List[ExperienceItem]:
        experience_items = []
        in_exp_section = False
        exp_lines = []
        
        # Section keywords
        exp_section_triggers = {"experience", "employment", "work", "history", "professional background"}
        other_section_triggers = {"education", "academic", "skills", "projects", "certifications", "interests", "languages"}

        for line in lines:
            line_lower = line.lower().strip()
            
            # Detect section boundary using word boundary checks
            if any(re.search(rf'\b{re.escape(trigger)}\b', line_lower) for trigger in exp_section_triggers):
                in_exp_section = True
                continue
            elif in_exp_section and any(re.search(rf'\b{re.escape(trigger)}\b', line_lower) for trigger in other_section_triggers):
                in_exp_section = False
                break
            
            if in_exp_section:
                exp_lines.append(line)

        # Parse lines in the experience section
        # Heuristic: Title + Company + Date + Description
        current_comp = None
        current_title = None
        current_start = None
        current_end = None
        current_desc = []

        date_pattern = r'\b(19\d{2}|20\d{2})\b'

        for idx, xline in enumerate(exp_lines):
            xline_lower = xline.lower()
            
            # Job Title detection (using common terms)
            is_title = any(keyword in xline_lower for keyword in ["engineer", "developer", "designer", "manager", "analyst", "consultant", "administrator", "lead", "architect", "programmer", "intern", "specialist"])
            # Date check
            dates = re.findall(date_pattern, xline)

            if is_title or (dates and current_comp is None):
                # If we already have a job record, save it first
                if current_comp or current_title:
                    experience_items.append(ExperienceItem(
                        company=current_comp or "Unknown Company",
                        title=current_title or "Unknown Role",
                        start_date=current_start,
                        end_date=current_end,
                        description=" ".join(current_desc) if current_desc else None
                    ))
                    current_comp, current_title, current_start, current_end = None, None, None, None
                    current_desc = []

                # Extract dates
                if dates:
                    if len(dates) >= 2:
                        current_start, current_end = dates[0], dates[1]
                    else:
                        current_end = dates[0]
                        if "present" in xline_lower:
                            current_start = dates[0]
                            current_end = "Present"
                
                # Split job title and company if separated by "at" or comma
                if " at " in xline:
                    parts = xline.split(" at ", 1)
                    current_title = parts[0].strip()
                    current_comp = parts[1].split(",")[0].strip()
                elif "," in xline:
                    parts = xline.split(",", 1)
                    current_title = parts[0].strip()
                    comp_candidate = parts[1].strip()
                    # Avoid treating dates/years as company names
                    comp_clean = re.sub(r'[\d\s\-\–\—to]+|present|current|now', '', comp_candidate.lower())
                    if len(comp_clean.strip()) > 2:
                        current_comp = comp_candidate
                else:
                    current_title = xline.strip()

                # If company name is not yet resolved, check previous line
                if idx > 0 and current_comp is None:
                    prev_line = exp_lines[idx - 1].strip()
                    if not re.search(date_pattern, prev_line) and len(prev_line.split()) <= 4:
                        current_comp = prev_line

            elif current_title is not None and not is_title:
                # Accumulate descriptions
                if len(xline.strip()) > 5:
                    # Check if it contains dates and looks like a company name
                    if any(keyword in xline_lower for keyword in ["inc.", "ltd.", "llc", "corp.", "corporation", "solutions", "technologies", "systems"]):
                        current_comp = xline.strip()
                    else:
                        current_desc.append(xline.strip())

        # Append last item
        if current_comp or current_title:
            experience_items.append(ExperienceItem(
                company=current_comp or "Unknown Company",
                title=current_title or "Unknown Role",
                start_date=current_start,
                end_date=current_end,
                description=" ".join(current_desc) if current_desc else None
            ))

        return experience_items
