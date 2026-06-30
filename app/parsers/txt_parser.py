import re
from typing import List, Optional
from app.parsers.base import BaseParser
from app.models.schemas import RawCandidate
from app.parsers.resume_parser import TECH_SKILLS_CATALOG
from app.utils.logging import logger

class TXTParser(BaseParser):
    def parse(self, file_path: str) -> RawCandidate:
        logger.info(f"Parsing recruiter notes TXT file: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            if not text.strip():
                logger.warning(f"TXT notes file is empty: {file_path}")
                return RawCandidate()

            return self._parse_text(text)
        except Exception as e:
            logger.error(f"Error parsing recruiter notes {file_path}: {e}")
            raise

    def _parse_text(self, text: str) -> RawCandidate:
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1. Extract Emails
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        emails = list(set([e.lower() for e in emails]))

        # 2. Extract Phone Numbers
        phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, text)
        phones = list(set([p.strip() for p in phones]))

        # 3. Extract Name (Heuristic: Look for Name: or Candidate: or first line)
        full_name = self._extract_name(lines)

        first_name, last_name = None, None
        if full_name:
            parts = full_name.split()
            if len(parts) > 0:
                first_name = parts[0]
            if len(parts) > 1:
                last_name = " ".join(parts[1:])

        # 4. Extract Country (Lookup by keyword in text)
        country = self._extract_country(text)

        # 5. Extract Skills
        skills = self._extract_skills(text)

        # Note: Recruiter notes typically don't have structured lists of education or experience
        # but if we find general mentions we could extract them. For simplicity and correctness,
        # we focus on basic fields, skills, emails, and phones.

        return RawCandidate(
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            emails=emails,
            phones=phones,
            skills=skills,
            education=[],
            experience=[],
            country=country
        )

    def _extract_name(self, lines: List[str]) -> Optional[str]:
        # Search for Name: [Name] or Candidate: [Name]
        for line in lines:
            match = re.match(r'^(?:candidate|name|candidate_name|candidate name)\s*:\s*(.+)$', line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Heuristic fall back: First line if it's short and doesn't contain email/phone/triggers
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 40 and not any(char in first_line for char in ["@", "|", "/"]) and not any(char.isdigit() for char in first_line):
                return first_line
        return None

    def _extract_country(self, text: str) -> Optional[str]:
        # Basic check
        import pycountry
        text_lower = text.lower()
        for country in pycountry.countries:
            c_name = country.name.lower()
            if len(c_name) > 3 and c_name in text_lower:
                return country.name
        return None

    def _extract_skills(self, text: str) -> List[str]:
        matched_skills = set()
        text_lower = text.lower()
        for key, canonical_name in TECH_SKILLS_CATALOG.items():
            pattern = rf'\b{re.escape(key)}\b'
            if re.search(pattern, text_lower):
                matched_skills.add(canonical_name)
        return sorted(list(matched_skills))
