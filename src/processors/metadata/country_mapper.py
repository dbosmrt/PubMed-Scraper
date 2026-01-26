"""
PubMed Scraper - Country Mapper

Extracts and normalizes country information from author affiliations.
Maps country names to ISO 3166-1 alpha-3 codes.
"""

import re
from typing import Optional

from src.shared.constants import COMMON_COUNTRY_ALIASES
from src.shared.logging import LoggerMixin


# Extended country mapping (name -> ISO 3166-1 alpha-3)
COUNTRY_MAP = {
    # Full names
    "afghanistan": "AFG",
    "albania": "ALB",
    "algeria": "DZA",
    "argentina": "ARG",
    "armenia": "ARM",
    "australia": "AUS",
    "austria": "AUT",
    "azerbaijan": "AZE",
    "bahrain": "BHR",
    "bangladesh": "BGD",
    "belarus": "BLR",
    "belgium": "BEL",
    "brazil": "BRA",
    "bulgaria": "BGR",
    "cameroon": "CMR",
    "canada": "CAN",
    "chile": "CHL",
    "china": "CHN",
    "colombia": "COL",
    "croatia": "HRV",
    "cuba": "CUB",
    "cyprus": "CYP",
    "czech republic": "CZE",
    "czechia": "CZE",
    "denmark": "DNK",
    "egypt": "EGY",
    "estonia": "EST",
    "ethiopia": "ETH",
    "finland": "FIN",
    "france": "FRA",
    "georgia": "GEO",
    "germany": "DEU",
    "ghana": "GHA",
    "greece": "GRC",
    "hong kong": "HKG",
    "hungary": "HUN",
    "iceland": "ISL",
    "india": "IND",
    "indonesia": "IDN",
    "iran": "IRN",
    "iraq": "IRQ",
    "ireland": "IRL",
    "israel": "ISR",
    "italy": "ITA",
    "japan": "JPN",
    "jordan": "JOR",
    "kazakhstan": "KAZ",
    "kenya": "KEN",
    "kuwait": "KWT",
    "latvia": "LVA",
    "lebanon": "LBN",
    "libya": "LBY",
    "lithuania": "LTU",
    "luxembourg": "LUX",
    "macau": "MAC",
    "malaysia": "MYS",
    "malta": "MLT",
    "mexico": "MEX",
    "morocco": "MAR",
    "nepal": "NPL",
    "netherlands": "NLD",
    "new zealand": "NZL",
    "nigeria": "NGA",
    "norway": "NOR",
    "oman": "OMN",
    "pakistan": "PAK",
    "palestine": "PSE",
    "peru": "PER",
    "philippines": "PHL",
    "poland": "POL",
    "portugal": "PRT",
    "qatar": "QAT",
    "romania": "ROU",
    "russia": "RUS",
    "russian federation": "RUS",
    "saudi arabia": "SAU",
    "serbia": "SRB",
    "singapore": "SGP",
    "slovakia": "SVK",
    "slovenia": "SVN",
    "south africa": "ZAF",
    "south korea": "KOR",
    "spain": "ESP",
    "sri lanka": "LKA",
    "sudan": "SDN",
    "sweden": "SWE",
    "switzerland": "CHE",
    "syria": "SYR",
    "taiwan": "TWN",
    "thailand": "THA",
    "tunisia": "TUN",
    "turkey": "TUR",
    "uganda": "UGA",
    "ukraine": "UKR",
    "united arab emirates": "ARE",
    "uae": "ARE",
    "united kingdom": "GBR",
    "united states": "USA",
    "uruguay": "URY",
    "uzbekistan": "UZB",
    "venezuela": "VEN",
    "vietnam": "VNM",
    "yemen": "YEM",
    "zimbabwe": "ZWE",
    # Common abbreviations and variations
    "usa": "USA",
    "u.s.a.": "USA",
    "u.s.": "USA",
    "us": "USA",
    "uk": "GBR",
    "u.k.": "GBR",
    "england": "GBR",
    "scotland": "GBR",
    "wales": "GBR",
    "northern ireland": "GBR",
    "deutschland": "DEU",
    "p.r. china": "CHN",
    "p.r.c.": "CHN",
    "prc": "CHN",
    "republic of korea": "KOR",
    "korea": "KOR",
    "r.o.c.": "TWN",
    "holland": "NLD",
    "the netherlands": "NLD",
    **COMMON_COUNTRY_ALIASES,
}


class CountryMapper(LoggerMixin):
    """
    Extracts country information from affiliation strings.

    Uses pattern matching and a comprehensive country name database
    to normalize country names to ISO codes.
    """

    def __init__(self) -> None:
        # Compile regex for efficiency
        self._country_pattern = self._build_pattern()

    def _build_pattern(self) -> re.Pattern:
        """Build regex pattern from country names."""
        # Sort by length (longest first) to match more specific names first
        countries = sorted(COUNTRY_MAP.keys(), key=len, reverse=True)
        # Escape special characters and join with |
        pattern = "|".join(re.escape(c) for c in countries)
        return re.compile(f"\\b({pattern})\\b", re.IGNORECASE)

    def extract_country(self, affiliation: str) -> Optional[str]:
        """
        Extract country code from affiliation string.

        Args:
            affiliation: Affiliation text

        Returns:
            ISO 3166-1 alpha-3 country code or None
        """
        if not affiliation:
            return None

        affiliation_lower = affiliation.lower()

        # Try pattern matching
        matches = self._country_pattern.findall(affiliation_lower)
        if matches:
            # Return the last match (country is usually at the end)
            country_name = matches[-1].lower()
            return COUNTRY_MAP.get(country_name)

        # Try to find country from common patterns
        # Pattern: "City, Country" or "City, State, Country"
        parts = [p.strip() for p in affiliation.split(",")]
        if parts:
            last_part = parts[-1].lower().strip(".")
            if last_part in COUNTRY_MAP:
                return COUNTRY_MAP[last_part]

        return None

    def extract_countries(self, affiliation: str) -> list[str]:
        """
        Extract all countries mentioned in affiliation.

        Args:
            affiliation: Affiliation text

        Returns:
            List of ISO country codes
        """
        if not affiliation:
            return []

        affiliation_lower = affiliation.lower()
        matches = self._country_pattern.findall(affiliation_lower)

        countries = []
        for match in matches:
            code = COUNTRY_MAP.get(match.lower())
            if code and code not in countries:
                countries.append(code)

        return countries

    def normalize_country(self, country: str) -> Optional[str]:
        """
        Normalize a country name to ISO code.

        Args:
            country: Country name or code

        Returns:
            ISO 3166-1 alpha-3 code or None
        """
        if not country:
            return None

        # Already a valid code?
        if country.upper() in COUNTRY_MAP.values():
            return country.upper()

        # Look up in map
        return COUNTRY_MAP.get(country.lower())

    def get_country_name(self, code: str) -> Optional[str]:
        """
        Get country name from ISO code.

        Args:
            code: ISO 3166-1 alpha-3 code

        Returns:
            Country name or None
        """
        # Reverse lookup (inefficient but rarely used)
        code_upper = code.upper()
        for name, c in COUNTRY_MAP.items():
            if c == code_upper:
                return name.title()
        return None


# Singleton instance
country_mapper = CountryMapper()
