# =============================================================================
# app/services/pakistan_plate_format.py — Pakistan-specific plate parsing
# =============================================================================
# UNIQUE FEATURE — Identifies the province, city, plate category (private /
# commercial / government / diplomatic / police / army) and the issue series
# from a recognized plate string.
#
# Pakistan plate format reference (consolidated from Excise & Taxation
# notifications across provinces, 2014–2024 series):
#
#   Punjab        : <CITY-CODE><LETTER>-<DIGITS>     e.g. LEA-1234, LXY-789
#                   (Lahore = LE*, Faisalabad = FD*, Multan = MN*, ...)
#   Sindh         : <CITY>-<DIGITS> or <PREFIX>-<DIGITS>  e.g. BJN-770, AVK-001
#                   Karachi = AAA..AZZ, BAA..BZZ; Hyderabad = HJ*, ...
#   KPK           : <LETTERS>-<DIGITS>               e.g. A-1234, AB-1234
#   Balochistan   : Q-XXXX, BAA-XXX, etc.
#   ICT (Islamabad): ICT-NN-NNNN                     e.g. ICT-17-1234
#   AJK           : AJK-<DIGITS>
#   Gilgit-Baltistan: GB-<DIGITS>
#   Government     : leading "GOVT" or "GP" prefix
#   Diplomatic     : "CD-" or "DP-" prefix
#   Army           : "ARMY", "FF", "FC", "PA" prefixes
#
# Plate-color category (visual, NOT in text):
#   White bg / black text  = private
#   Yellow bg / black text = commercial (taxis, rickshaw, public transport)
#   Green  bg / white text = government
#   Blue   bg / white text = diplomatic / corps
#   Red    bg / white text = army / president / governor
#
# This module gives the textual classification — color is detected in
# fake_plate_detector.py.
# =============================================================================

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# City code dictionary (subset — most common; extend as needed)
# ---------------------------------------------------------------------------
PUNJAB_CITY_CODES = {
    "LE": "Lahore", "LX": "Lahore", "LH": "Lahore", "LO": "Lahore",
    "FD": "Faisalabad", "FX": "Faisalabad",
    "MN": "Multan", "MX": "Multan",
    "RW": "Rawalpindi", "RI": "Rawalpindi", "RX": "Rawalpindi",
    "GJ": "Gujranwala", "GW": "Gujranwala",
    "SL": "Sialkot", "SK": "Sialkot",
    "BW": "Bahawalpur",
    "SG": "Sargodha",
    "DG": "Dera Ghazi Khan",
    "OK": "Okara",
    "KS": "Kasur",
    "JH": "Jhang",
    "SH": "Sheikhupura",
    "AT": "Attock",
    "CW": "Chakwal",
    "JL": "Jhelum",
    "TT": "Toba Tek Singh",
    "MH": "Mianwali",
    "VH": "Vehari",
    "RY": "Rahim Yar Khan",
    "PK": "Pakpattan",
    "NK": "Nankana Sahib",
}

SINDH_CITY_CODES = {
    # Karachi series — A**, B**, C**, ... (huge range, use prefix letter)
    "AA": "Karachi", "AB": "Karachi", "AC": "Karachi", "AD": "Karachi",
    "AE": "Karachi", "AF": "Karachi", "AG": "Karachi", "AH": "Karachi",
    "AJ": "Karachi", "AK": "Karachi", "AL": "Karachi", "AM": "Karachi",
    "AN": "Karachi", "AP": "Karachi", "AR": "Karachi", "AS": "Karachi",
    "AT": "Karachi", "AV": "Karachi", "AW": "Karachi", "AX": "Karachi",
    "AY": "Karachi", "AZ": "Karachi",
    "BA": "Karachi", "BB": "Karachi", "BC": "Karachi", "BD": "Karachi",
    "BE": "Karachi", "BF": "Karachi", "BG": "Karachi", "BH": "Karachi",
    "BJ": "Karachi", "BK": "Karachi", "BL": "Karachi", "BM": "Karachi",
    "BN": "Karachi", "BP": "Karachi",
    # Interior Sindh
    "HJ": "Hyderabad", "HK": "Hyderabad",
    "SU": "Sukkur",
    "LK": "Larkana",
    "NW": "Nawabshah",
    "MR": "Mirpurkhas",
    "KH": "Khairpur",
    "BD": "Badin",
    "TH": "Thatta",
    "JC": "Jacobabad",
    "SB": "Shaheed Benazirabad",
}

KPK_CITY_CODES = {
    "A":   "Peshawar",
    "B":   "Mardan",
    "C":   "Kohat",
    "D":   "Bannu",
    "E":   "DI Khan",
    "F":   "Abbottabad",
    "G":   "Mansehra",
    "H":   "Swat",
    "J":   "Chitral",
    "K":   "Malakand",
    "L":   "Hazara",
    "PR":  "Peshawar",
    "MR":  "Mardan",
    "SW":  "Swat",
    "AB":  "Abbottabad",
}

BALOCHISTAN_CITY_CODES = {
    "Q":   "Quetta",
    "BA":  "Quetta",
    "GW":  "Gwadar",
    "TM":  "Turbat",
    "KL":  "Khuzdar",
    "ZB":  "Zhob",
    "SB":  "Sibi",
    "MS":  "Mastung",
    "PB":  "Panjgur",
}


# ---------------------------------------------------------------------------
# Pakistan plate REGEX patterns (ordered: more specific first)
# ---------------------------------------------------------------------------
PATTERNS = [
    # ICT (Islamabad) — ICT-17-1234
    ("ICT", re.compile(r"^ICT[-\s]?\d{2}[-\s]?\d{1,4}$")),
    ("AJK", re.compile(r"^AJK[-\s]?\d{1,4}$")),
    ("GB",  re.compile(r"^GB[-\s]?\d{1,4}$")),
    # Diplomatic
    ("DIPLO", re.compile(r"^(CD|DP)[-\s]?\d{1,4}$")),
    # Government
    ("GOVT",  re.compile(r"^(GOVT|GP)[-\s]?\d{1,4}$")),
    # Army / paramilitary
    ("ARMY",  re.compile(r"^(ARMY|PA|FF|FC|SSG)[-\s]?\d{1,5}$")),
    # Punjab / Sindh / KPK / Balochistan generic civilian
    ("CIVILIAN_3", re.compile(r"^([A-Z]{2,3})[-\s]?(\d{1,4})$")),
    ("CIVILIAN_2", re.compile(r"^([A-Z]{1,2})[-\s]?(\d{1,4})$")),
    # Commercial Karachi short style: 7777-A
    ("COMMERCIAL_REV", re.compile(r"^(\d{3,4})[-\s]?([A-Z]{1,3})$")),
]


@dataclass
class PlateInfo:
    plate_text: str
    is_valid_format: bool
    province: str | None
    city: str | None
    category: str            # private | commercial | government | diplomatic | army | unknown
    series: str | None       # letter prefix
    number: str | None       # digit suffix
    confidence: float        # how confident we are about this classification 0..1
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "plate_text": self.plate_text,
            "is_valid_format": self.is_valid_format,
            "province": self.province,
            "city": self.city,
            "category": self.category,
            "series": self.series,
            "number": self.number,
            "format_confidence": round(self.confidence, 3),
            "notes": self.notes,
        }


def _classify_city(prefix: str) -> tuple[str | None, str | None]:
    """Return (province, city) for a given letter prefix."""
    p = prefix.upper()
    if p in PUNJAB_CITY_CODES:
        return ("Punjab", PUNJAB_CITY_CODES[p])
    if p[:2] in PUNJAB_CITY_CODES:
        return ("Punjab", PUNJAB_CITY_CODES[p[:2]])
    if p in SINDH_CITY_CODES:
        return ("Sindh", SINDH_CITY_CODES[p])
    if p[:2] in SINDH_CITY_CODES:
        return ("Sindh", SINDH_CITY_CODES[p[:2]])
    if p in KPK_CITY_CODES:
        return ("Khyber Pakhtunkhwa", KPK_CITY_CODES[p])
    if p[:2] in KPK_CITY_CODES:
        return ("Khyber Pakhtunkhwa", KPK_CITY_CODES[p[:2]])
    if p[:1] in KPK_CITY_CODES:
        return ("Khyber Pakhtunkhwa", KPK_CITY_CODES[p[:1]])
    if p in BALOCHISTAN_CITY_CODES:
        return ("Balochistan", BALOCHISTAN_CITY_CODES[p])
    if p[:2] in BALOCHISTAN_CITY_CODES:
        return ("Balochistan", BALOCHISTAN_CITY_CODES[p[:2]])
    if p[:1] in BALOCHISTAN_CITY_CODES:
        return ("Balochistan", BALOCHISTAN_CITY_CODES[p[:1]])
    return (None, None)


def parse_plate(plate_text: str) -> PlateInfo:
    """
    Identify the Pakistani plate's province, city, and category.

    `plate_text` should be the cleaned OCR string (uppercase, alphanumeric).
    Hyphens/spaces inside are tolerated by the regex.
    """
    if not plate_text:
        return PlateInfo(
            plate_text="",
            is_valid_format=False,
            province=None, city=None,
            category="unknown",
            series=None, number=None,
            confidence=0.0,
            notes="empty",
        )

    text = re.sub(r"\s+", "", plate_text.upper())
    # Re-insert canonical hyphen for matching: split letters/digits
    canonical = re.sub(r"([A-Z]+)(\d+)", r"\1-\2", text)
    canonical = re.sub(r"(\d+)([A-Z]+)", r"\1-\2", canonical)

    for label, pat in PATTERNS:
        m = pat.match(canonical)
        if not m:
            continue

        if label == "ICT":
            return PlateInfo(
                plate_text=canonical, is_valid_format=True,
                province="Islamabad Capital Territory", city="Islamabad",
                category="private", series="ICT",
                number=re.sub(r"[^0-9]", "", canonical)[2:],
                confidence=0.95,
            )
        if label == "AJK":
            return PlateInfo(
                plate_text=canonical, is_valid_format=True,
                province="Azad Jammu & Kashmir", city=None,
                category="private", series="AJK",
                number=re.sub(r"[^0-9]", "", canonical),
                confidence=0.92,
            )
        if label == "GB":
            return PlateInfo(
                plate_text=canonical, is_valid_format=True,
                province="Gilgit-Baltistan", city=None,
                category="private", series="GB",
                number=re.sub(r"[^0-9]", "", canonical),
                confidence=0.9,
            )
        if label == "DIPLO":
            return PlateInfo(
                plate_text=canonical, is_valid_format=True,
                province="Federal", city="Islamabad",
                category="diplomatic", series=canonical.split("-")[0],
                number=canonical.split("-")[-1],
                confidence=0.95,
            )
        if label == "GOVT":
            return PlateInfo(
                plate_text=canonical, is_valid_format=True,
                province="Federal", city=None,
                category="government", series=canonical.split("-")[0],
                number=canonical.split("-")[-1],
                confidence=0.9,
            )
        if label == "ARMY":
            return PlateInfo(
                plate_text=canonical, is_valid_format=True,
                province="Federal", city=None,
                category="army", series=canonical.split("-")[0],
                number=canonical.split("-")[-1],
                confidence=0.9,
            )
        if label in ("CIVILIAN_3", "CIVILIAN_2"):
            prefix, number = m.group(1), m.group(2)
            province, city = _classify_city(prefix)
            return PlateInfo(
                plate_text=canonical,
                is_valid_format=province is not None,
                province=province, city=city,
                category="private",
                series=prefix, number=number,
                confidence=0.85 if province else 0.4,
                notes="" if province else "unknown city/province code",
            )
        if label == "COMMERCIAL_REV":
            number, prefix = m.group(1), m.group(2)
            province, city = _classify_city(prefix)
            return PlateInfo(
                plate_text=canonical,
                is_valid_format=True,
                province=province or "Sindh", city=city or "Karachi",
                category="commercial",
                series=prefix, number=number,
                confidence=0.7,
                notes="commercial reversed-format",
            )

    return PlateInfo(
        plate_text=text, is_valid_format=False,
        province=None, city=None,
        category="unknown", series=None, number=None,
        confidence=0.2,
        notes="no Pakistan format matched",
    )
