import re
import phonenumbers
from dateutil import parser as date_parser
import pycountry
from app.utils.logging import logger
from app.parsers.resume_parser import TECH_SKILLS_CATALOG

def normalize_phone(phone: str, default_region: str = "US") -> str:
    """
    Normalizes a phone number to E164 format.
    E.g., +1 (555) 555-5555 -> +15555555555
    If parsing fails, returns the cleaned original phone number.
    """
    if not phone:
        return ""
    
    cleaned = re.sub(r'[^\d+x-]', '', phone.strip())
    
    try:
        # Check if number already has country code (starts with +)
        if cleaned.startswith("+"):
            parsed = phonenumbers.parse(cleaned, None)
        else:
            parsed = phonenumbers.parse(cleaned, default_region)
            # If invalid for default region, check if it's an international number missing '+' prefix
            if not phonenumbers.is_valid_number(parsed):
                try:
                    alt_parsed = phonenumbers.parse("+" + cleaned, None)
                    if phonenumbers.is_valid_number(alt_parsed):
                        parsed = alt_parsed
                except Exception:
                    pass
            
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception as e:
        logger.debug(f"Phonenumbers library failed to parse '{phone}': {e}")
    
    # Fallback: return digits only, optionally keeping leading '+'
    digits = re.sub(r'[^\d+]', '', phone.strip())
    return digits

def normalize_date(date_str: str) -> str:
    """
    Normalizes a date string to ISO format YYYY-MM-DD.
    E.g. 'May 2018' -> '2018-05-01'
    E.g. '2020' -> '2020-01-01'
    Returns the original string if parsing fails or for relative dates like 'Present'.
    """
    if not date_str:
        return ""
    
    val = date_str.strip()
    if val.lower() in ["present", "current", "now", "to present"]:
        return "Present"
        
    import datetime
    try:
        # Attempt to parse year-only values first to avoid dateutil default month issues
        if re.match(r'^\d{4}$', val):
            return f"{val}-01-01"
            
        parsed = date_parser.parse(val, default=datetime.datetime(2000, 1, 1))
        if parsed:
            # Format as YYYY-MM-DD
            return parsed.strftime("%Y-%m-%d")
    except Exception as e:
        logger.debug(f"Dateutil failed to parse date string '{date_str}': {e}")
        
    return val

def normalize_country(country_str: str) -> str:
    """
    Normalizes a country name to its standard name using pycountry.
    E.g., 'USA' -> 'United States', 'germany' -> 'Germany'
    Returns the original string if country is not recognized.
    """
    if not country_str:
        return ""
        
    clean_val = country_str.strip().lower()
    
    # Direct short codes mapping
    shortcuts = {
        "usa": "United States",
        "us": "United States",
        "uk": "United Kingdom",
        "uae": "United Arab Emirates",
        "in": "India",
        "de": "Germany",
        "fr": "France",
        "ca": "Canada",
        "au": "Australia",
    }
    if clean_val in shortcuts:
        return shortcuts[clean_val]
        
    try:
        # Attempt exact lookup by alpha_2, alpha_3 or name
        for country in pycountry.countries:
            if country.name.lower() == clean_val:
                return country.name
            if hasattr(country, 'official_name') and country.official_name.lower() == clean_val:
                return country.name
            if country.alpha_2.lower() == clean_val:
                return country.name
            if country.alpha_3.lower() == clean_val:
                return country.name
                
        # Substring search
        for country in pycountry.countries:
            if clean_val in country.name.lower():
                return country.name
    except Exception as e:
        logger.debug(f"Pycountry lookup error for '{country_str}': {e}")
        
    # Return capitalized title if nothing matched
    return country_str.title()

def normalize_email(email_str: str) -> str:
    """
    Normalizes an email address.
    """
    if not email_str:
        return ""
    email_clean = email_str.strip().lower()
    # Simple regex validation check
    if re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email_clean):
        return email_clean
    return email_clean

def normalize_skill(skill_str: str) -> str:
    """
    Normalizes a skill name by searching in our technology catalog.
    """
    if not skill_str:
        return ""
    clean_val = skill_str.strip()
    catalog_match = TECH_SKILLS_CATALOG.get(clean_val.lower())
    if catalog_match:
        return catalog_match
    return clean_val
