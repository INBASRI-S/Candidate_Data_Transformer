import os
import httpx
import pycountry
from typing import Optional, List, Dict, Any
from app.parsers.base import BaseParser
from app.models.schemas import RawCandidate, ExperienceItem
from app.parsers.resume_parser import TECH_SKILLS_CATALOG
from app.utils.logging import logger

class GitHubParser(BaseParser):
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "User-Agent": "Candidate-Data-Transformer-App/1.0"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def parse(self, username: str) -> RawCandidate:
        logger.info(f"Fetching GitHub profile for user: {username}")
        if not username or not username.strip():
            logger.warning("Empty GitHub username provided")
            return RawCandidate()

        username = username.strip()
        client = httpx.Client(headers=self.headers, timeout=10.0)
        
        try:
            # 1. Fetch User Info
            user_url = f"https://api.github.com/users/{username}"
            logger.debug(f"Calling GitHub API: {user_url}")
            user_resp = client.get(user_url)
            
            if user_resp.status_code == 404:
                logger.warning(f"GitHub user not found: {username}")
                return RawCandidate()
            elif user_resp.status_code != 200:
                logger.error(f"GitHub API returned error {user_resp.status_code}: {user_resp.text}")
                return RawCandidate()

            user_data = user_resp.json()

            # 2. Fetch User Repos (to extract programming languages/skills)
            repos_url = f"https://api.github.com/users/{username}/repos?per_page=50&sort=updated"
            logger.debug(f"Calling GitHub API: {repos_url}")
            repos_resp = client.get(repos_url)
            
            languages = set()
            if repos_resp.status_code == 200:
                repos = repos_resp.json()
                for repo in repos:
                    lang = repo.get("language")
                    if lang:
                        languages.add(lang)
            else:
                logger.warning(f"Failed to fetch repositories for GitHub user {username}")

            # Map the response data to RawCandidate
            return self._map_github_data(user_data, list(languages))
        except Exception as e:
            logger.error(f"Error parsing GitHub profile for {username}: {e}")
            # Do not fail the whole pipeline if GitHub fails (e.g. rate-limit or network offline)
            # return empty candidate
            return RawCandidate()
        finally:
            client.close()

    def _map_github_data(self, user_data: Dict[str, Any], languages: List[str]) -> RawCandidate:
        full_name = user_data.get("name")
        first_name, last_name = None, None
        if full_name:
            parts = full_name.split()
            if len(parts) > 0:
                first_name = parts[0]
            if len(parts) > 1:
                last_name = " ".join(parts[1:])

        # Emails
        emails = []
        email = user_data.get("email")
        if email:
            emails.append(email.lower())

        # Location/Country Heuristic
        country = None
        location = user_data.get("location")
        if location:
            country = self._extract_country_from_location(location)

        # Skills
        # Add public languages, check bio for skills
        skills_set = set()
        bio = user_data.get("bio") or ""
        
        # Add languages detected from repos
        for lang in languages:
            canonical = TECH_SKILLS_CATALOG.get(lang.lower())
            if canonical:
                skills_set.add(canonical)
            else:
                skills_set.add(lang)

        # Scan bio for other skills
        bio_lower = bio.lower()
        for key, canonical_name in TECH_SKILLS_CATALOG.items():
            if f" {key} " in f" {bio_lower} " or f",{key}" in bio_lower or f"{key}," in bio_lower:
                skills_set.add(canonical_name)

        # Experience
        experience = []
        company = user_data.get("company")
        if company:
            # If candidate lists a company in profile, create a simple experience entry
            # Strip leading '@' if present (standard github company mention)
            comp_name = company.lstrip("@").strip()
            experience.append(ExperienceItem(
                company=comp_name,
                title="Software Engineer", # Generic title for github profile
                description=f"GitHub Profile Company association: {company}. Bio: {bio}" if bio else f"GitHub Profile Company: {company}"
            ))

        return RawCandidate(
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            emails=emails,
            phones=[],
            skills=sorted(list(skills_set)),
            education=[],
            experience=experience,
            country=country
        )

    def _extract_country_from_location(self, location: str) -> Optional[str]:
        # Heuristic: split by comma, check if last part matches standard country
        parts = [p.strip().lower() for p in location.split(",")]
        for part in reversed(parts):
            for country in pycountry.countries:
                if country.name.lower() == part:
                    return country.name
                # Common country abbreviation
                if part in ["usa", "us"]:
                    return "United States"
                if part in ["uk", "united kingdom"]:
                    return "United Kingdom"
        
        # General substring search if split didn't match
        location_lower = location.lower()
        for country in pycountry.countries:
            if country.name.lower() in location_lower:
                return country.name
        
        return None
