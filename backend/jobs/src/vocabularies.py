"""Fixed value lists shared by preferences validation, the evaluator and the fetcher filters.

This is the single backend source for every slug stored in the database or sent to the LLM.
The frontend keeps matching human-readable labels in ``lib/profile/options.ts``.
"""

from dataclasses import dataclass

DECLINE_TO_ANSWER = "decline_to_answer"

SENIORITY_LEVELS: tuple[str, ...] = (
    "intern",
    "entry",
    "mid",
    "senior",
    "staff_principal",
    "lead_manager",
    "director",
    "vp_plus",
)

WORK_ARRANGEMENTS: tuple[str, ...] = ("remote", "hybrid", "onsite")

JOB_TYPES: tuple[str, ...] = ("full_time", "part_time", "contract", "internship", "temporary")

GENDER_OPTIONS: tuple[str, ...] = ("female", "male", "non_binary", DECLINE_TO_ANSWER)

EEO_ANSWER_OPTIONS: dict[str, tuple[str, ...]] = {
    "race_ethnicity": (
        "american_indian_or_alaska_native",
        "asian",
        "black_or_african_american",
        "hispanic_or_latino",
        "native_hawaiian_or_pacific_islander",
        "white",
        "two_or_more_races",
        DECLINE_TO_ANSWER,
    ),
    "veteran_status": ("protected_veteran", "not_protected_veteran", DECLINE_TO_ANSWER),
    "disability_status": ("yes", "no", DECLINE_TO_ANSWER),
    "work_authorization": ("authorized", "not_authorized", DECLINE_TO_ANSWER),
    "needs_visa_sponsorship": ("yes", "no", DECLINE_TO_ANSWER),
}

EEO_QUESTION_KEYS: tuple[str, ...] = tuple(EEO_ANSWER_OPTIONS)

ATS_PROVIDERS: tuple[str, ...] = ("greenhouse", "lever", "ashby", "workday", "icims", "bamboohr")

BOARD_DISCOVERY_SOURCES: tuple[str, ...] = ("ats_sweep", "google_jobs")


@dataclass(frozen=True)
class Country:
    """An ISO 3166-1 alpha-2 country with extra names used when matching posting locations."""

    code: str
    name: str
    aliases: tuple[str, ...] = ()

    @property
    def match_terms(self) -> tuple[str, ...]:
        """Lower-cased name and aliases; the ISO code is matched separately (case-sensitive)."""
        return tuple(term.lower() for term in (self.name, *self.aliases))


# Aliases for location matching; countries not listed here match on name and code only.
# fmt: off
_COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "AE": ("UAE", "Emirates", "Dubai", "Abu Dhabi"),
    "BO": ("Bolivia",),
    "BR": ("Brasil",),
    "CD": ("DR Congo", "DRC", "Congo-Kinshasa"),
    "CG": ("Congo-Brazzaville",),
    "CI": ("Ivory Coast", "Cote d'Ivoire"),
    "CZ": ("Czech Republic",),
    "DE": ("Deutschland",),
    "ES": ("España", "Espana"),
    "GB": ("UK", "U.K.", "Great Britain", "Britain", "England", "Scotland", "Wales",
           "Northern Ireland"),
    "HK": ("Hong Kong SAR",),
    "IR": ("Iran",),
    "KP": ("North Korea",),
    "KR": ("South Korea", "Korea"),
    "LA": ("Laos",),
    "MD": ("Moldova",),
    "MX": ("México",),
    "NL": ("Holland", "The Netherlands"),
    "PS": ("Palestine",),
    "RU": ("Russia",),
    "SG": ("Singapore City",),
    "SY": ("Syria",),
    "TR": ("Turkey", "Türkiye"),
    "TW": ("Taiwan ROC",),
    "TZ": ("Tanzania",),
    "US": ("USA", "U.S.", "U.S.A.", "United States of America", "America"),
    "VE": ("Venezuela",),
    "VN": ("Viet Nam",),
}

_COUNTRY_NAMES: tuple[tuple[str, str], ...] = (
    ("AD", "Andorra"), ("AE", "United Arab Emirates"), ("AF", "Afghanistan"),
    ("AG", "Antigua and Barbuda"), ("AI", "Anguilla"), ("AL", "Albania"), ("AM", "Armenia"),
    ("AO", "Angola"), ("AQ", "Antarctica"), ("AR", "Argentina"), ("AS", "American Samoa"),
    ("AT", "Austria"), ("AU", "Australia"), ("AW", "Aruba"), ("AX", "Åland Islands"),
    ("AZ", "Azerbaijan"), ("BA", "Bosnia and Herzegovina"), ("BB", "Barbados"),
    ("BD", "Bangladesh"), ("BE", "Belgium"), ("BF", "Burkina Faso"), ("BG", "Bulgaria"),
    ("BH", "Bahrain"), ("BI", "Burundi"), ("BJ", "Benin"), ("BL", "Saint Barthélemy"),
    ("BM", "Bermuda"), ("BN", "Brunei Darussalam"), ("BO", "Bolivia, Plurinational State of"),
    ("BQ", "Bonaire, Sint Eustatius and Saba"), ("BR", "Brazil"), ("BS", "Bahamas"),
    ("BT", "Bhutan"), ("BV", "Bouvet Island"), ("BW", "Botswana"), ("BY", "Belarus"),
    ("BZ", "Belize"), ("CA", "Canada"), ("CC", "Cocos (Keeling) Islands"),
    ("CD", "Congo, Democratic Republic of the"), ("CF", "Central African Republic"),
    ("CG", "Congo"), ("CH", "Switzerland"), ("CI", "Côte d'Ivoire"), ("CK", "Cook Islands"),
    ("CL", "Chile"), ("CM", "Cameroon"), ("CN", "China"), ("CO", "Colombia"),
    ("CR", "Costa Rica"), ("CU", "Cuba"), ("CV", "Cabo Verde"), ("CW", "Curaçao"),
    ("CX", "Christmas Island"), ("CY", "Cyprus"), ("CZ", "Czechia"), ("DE", "Germany"),
    ("DJ", "Djibouti"), ("DK", "Denmark"), ("DM", "Dominica"), ("DO", "Dominican Republic"),
    ("DZ", "Algeria"), ("EC", "Ecuador"), ("EE", "Estonia"), ("EG", "Egypt"),
    ("EH", "Western Sahara"), ("ER", "Eritrea"), ("ES", "Spain"), ("ET", "Ethiopia"),
    ("FI", "Finland"), ("FJ", "Fiji"), ("FK", "Falkland Islands (Malvinas)"),
    ("FM", "Micronesia, Federated States of"), ("FO", "Faroe Islands"), ("FR", "France"),
    ("GA", "Gabon"), ("GB", "United Kingdom"), ("GD", "Grenada"), ("GE", "Georgia"),
    ("GF", "French Guiana"), ("GG", "Guernsey"), ("GH", "Ghana"), ("GI", "Gibraltar"),
    ("GL", "Greenland"), ("GM", "Gambia"), ("GN", "Guinea"), ("GP", "Guadeloupe"),
    ("GQ", "Equatorial Guinea"), ("GR", "Greece"),
    ("GS", "South Georgia and the South Sandwich Islands"), ("GT", "Guatemala"),
    ("GU", "Guam"), ("GW", "Guinea-Bissau"), ("GY", "Guyana"), ("HK", "Hong Kong"),
    ("HM", "Heard Island and McDonald Islands"), ("HN", "Honduras"), ("HR", "Croatia"),
    ("HT", "Haiti"), ("HU", "Hungary"), ("ID", "Indonesia"), ("IE", "Ireland"),
    ("IL", "Israel"), ("IM", "Isle of Man"), ("IN", "India"),
    ("IO", "British Indian Ocean Territory"), ("IQ", "Iraq"),
    ("IR", "Iran, Islamic Republic of"), ("IS", "Iceland"), ("IT", "Italy"), ("JE", "Jersey"),
    ("JM", "Jamaica"), ("JO", "Jordan"), ("JP", "Japan"), ("KE", "Kenya"),
    ("KG", "Kyrgyzstan"), ("KH", "Cambodia"), ("KI", "Kiribati"), ("KM", "Comoros"),
    ("KN", "Saint Kitts and Nevis"), ("KP", "Korea, Democratic People's Republic of"),
    ("KR", "Korea, Republic of"), ("KW", "Kuwait"), ("KY", "Cayman Islands"),
    ("KZ", "Kazakhstan"), ("LA", "Lao People's Democratic Republic"), ("LB", "Lebanon"),
    ("LC", "Saint Lucia"), ("LI", "Liechtenstein"), ("LK", "Sri Lanka"), ("LR", "Liberia"),
    ("LS", "Lesotho"), ("LT", "Lithuania"), ("LU", "Luxembourg"), ("LV", "Latvia"),
    ("LY", "Libya"), ("MA", "Morocco"), ("MC", "Monaco"), ("MD", "Moldova, Republic of"),
    ("ME", "Montenegro"), ("MF", "Saint Martin (French part)"), ("MG", "Madagascar"),
    ("MH", "Marshall Islands"), ("MK", "North Macedonia"), ("ML", "Mali"), ("MM", "Myanmar"),
    ("MN", "Mongolia"), ("MO", "Macao"), ("MP", "Northern Mariana Islands"),
    ("MQ", "Martinique"), ("MR", "Mauritania"), ("MS", "Montserrat"), ("MT", "Malta"),
    ("MU", "Mauritius"), ("MV", "Maldives"), ("MW", "Malawi"), ("MX", "Mexico"),
    ("MY", "Malaysia"), ("MZ", "Mozambique"), ("NA", "Namibia"), ("NC", "New Caledonia"),
    ("NE", "Niger"), ("NF", "Norfolk Island"), ("NG", "Nigeria"), ("NI", "Nicaragua"),
    ("NL", "Netherlands"), ("NO", "Norway"), ("NP", "Nepal"), ("NR", "Nauru"), ("NU", "Niue"),
    ("NZ", "New Zealand"), ("OM", "Oman"), ("PA", "Panama"), ("PE", "Peru"),
    ("PF", "French Polynesia"), ("PG", "Papua New Guinea"), ("PH", "Philippines"),
    ("PK", "Pakistan"), ("PL", "Poland"), ("PM", "Saint Pierre and Miquelon"),
    ("PN", "Pitcairn"), ("PR", "Puerto Rico"), ("PS", "Palestine, State of"),
    ("PT", "Portugal"), ("PW", "Palau"), ("PY", "Paraguay"), ("QA", "Qatar"),
    ("RE", "Réunion"), ("RO", "Romania"), ("RS", "Serbia"), ("RU", "Russian Federation"),
    ("RW", "Rwanda"), ("SA", "Saudi Arabia"), ("SB", "Solomon Islands"), ("SC", "Seychelles"),
    ("SD", "Sudan"), ("SE", "Sweden"), ("SG", "Singapore"),
    ("SH", "Saint Helena, Ascension and Tristan da Cunha"), ("SI", "Slovenia"),
    ("SJ", "Svalbard and Jan Mayen"), ("SK", "Slovakia"), ("SL", "Sierra Leone"),
    ("SM", "San Marino"), ("SN", "Senegal"), ("SO", "Somalia"), ("SR", "Suriname"),
    ("SS", "South Sudan"), ("ST", "Sao Tome and Principe"), ("SV", "El Salvador"),
    ("SX", "Sint Maarten (Dutch part)"), ("SY", "Syrian Arab Republic"), ("SZ", "Eswatini"),
    ("TC", "Turks and Caicos Islands"), ("TD", "Chad"),
    ("TF", "French Southern Territories"), ("TG", "Togo"), ("TH", "Thailand"),
    ("TJ", "Tajikistan"), ("TK", "Tokelau"), ("TL", "Timor-Leste"), ("TM", "Turkmenistan"),
    ("TN", "Tunisia"), ("TO", "Tonga"), ("TR", "Türkiye"), ("TT", "Trinidad and Tobago"),
    ("TV", "Tuvalu"), ("TW", "Taiwan"), ("TZ", "Tanzania, United Republic of"),
    ("UA", "Ukraine"), ("UG", "Uganda"), ("UM", "United States Minor Outlying Islands"),
    ("US", "United States"), ("UY", "Uruguay"), ("UZ", "Uzbekistan"),
    ("VA", "Holy See"), ("VC", "Saint Vincent and the Grenadines"),
    ("VE", "Venezuela, Bolivarian Republic of"), ("VG", "Virgin Islands (British)"),
    ("VI", "Virgin Islands (U.S.)"), ("VN", "Vietnam"), ("VU", "Vanuatu"),
    ("WF", "Wallis and Futuna"), ("WS", "Samoa"), ("YE", "Yemen"), ("YT", "Mayotte"),
    ("ZA", "South Africa"), ("ZM", "Zambia"), ("ZW", "Zimbabwe"),
)

COUNTRIES: dict[str, Country] = {
    code: Country(code=code, name=name, aliases=_COUNTRY_ALIASES.get(code, ()))
    for code, name in _COUNTRY_NAMES
}

# Active ISO 4217 currencies (code -> English name).
CURRENCIES: dict[str, str] = {
    "AED": "UAE Dirham", "AFN": "Afghani", "ALL": "Lek", "AMD": "Armenian Dram",
    "AOA": "Kwanza", "ARS": "Argentine Peso", "AUD": "Australian Dollar",
    "AWG": "Aruban Florin", "AZN": "Azerbaijan Manat", "BAM": "Convertible Mark",
    "BBD": "Barbados Dollar", "BDT": "Taka", "BGN": "Bulgarian Lev", "BHD": "Bahraini Dinar",
    "BIF": "Burundi Franc", "BMD": "Bermudian Dollar", "BND": "Brunei Dollar",
    "BOB": "Boliviano", "BRL": "Brazilian Real", "BSD": "Bahamian Dollar", "BTN": "Ngultrum",
    "BWP": "Pula", "BYN": "Belarusian Ruble", "BZD": "Belize Dollar",
    "CAD": "Canadian Dollar", "CDF": "Congolese Franc", "CHF": "Swiss Franc",
    "CLP": "Chilean Peso", "CNY": "Yuan Renminbi", "COP": "Colombian Peso",
    "CRC": "Costa Rican Colon", "CUP": "Cuban Peso", "CVE": "Cabo Verde Escudo",
    "CZK": "Czech Koruna", "DJF": "Djibouti Franc", "DKK": "Danish Krone",
    "DOP": "Dominican Peso", "DZD": "Algerian Dinar", "EGP": "Egyptian Pound",
    "ERN": "Nakfa", "ETB": "Ethiopian Birr", "EUR": "Euro", "FJD": "Fiji Dollar",
    "FKP": "Falkland Islands Pound", "GBP": "Pound Sterling", "GEL": "Lari",
    "GHS": "Ghana Cedi", "GIP": "Gibraltar Pound", "GMD": "Dalasi", "GNF": "Guinean Franc",
    "GTQ": "Quetzal", "GYD": "Guyana Dollar", "HKD": "Hong Kong Dollar", "HNL": "Lempira",
    "HTG": "Gourde", "HUF": "Forint", "IDR": "Rupiah", "ILS": "New Israeli Sheqel",
    "INR": "Indian Rupee", "IQD": "Iraqi Dinar", "IRR": "Iranian Rial",
    "ISK": "Iceland Krona", "JMD": "Jamaican Dollar", "JOD": "Jordanian Dinar", "JPY": "Yen",
    "KES": "Kenyan Shilling", "KGS": "Som", "KHR": "Riel", "KMF": "Comorian Franc",
    "KPW": "North Korean Won", "KRW": "Won", "KWD": "Kuwaiti Dinar",
    "KYD": "Cayman Islands Dollar", "KZT": "Tenge", "LAK": "Lao Kip", "LBP": "Lebanese Pound",
    "LKR": "Sri Lanka Rupee", "LRD": "Liberian Dollar", "LSL": "Loti", "LYD": "Libyan Dinar",
    "MAD": "Moroccan Dirham", "MDL": "Moldovan Leu", "MGA": "Malagasy Ariary",
    "MKD": "Denar", "MMK": "Kyat", "MNT": "Tugrik", "MOP": "Pataca", "MRU": "Ouguiya",
    "MUR": "Mauritius Rupee", "MVR": "Rufiyaa", "MWK": "Malawi Kwacha",
    "MXN": "Mexican Peso", "MYR": "Malaysian Ringgit", "MZN": "Mozambique Metical",
    "NAD": "Namibia Dollar", "NGN": "Naira", "NIO": "Cordoba Oro", "NOK": "Norwegian Krone",
    "NPR": "Nepalese Rupee", "NZD": "New Zealand Dollar", "OMR": "Rial Omani",
    "PAB": "Balboa", "PEN": "Sol", "PGK": "Kina", "PHP": "Philippine Peso",
    "PKR": "Pakistan Rupee", "PLN": "Zloty", "PYG": "Guarani", "QAR": "Qatari Rial",
    "RON": "Romanian Leu", "RSD": "Serbian Dinar", "RUB": "Russian Ruble",
    "RWF": "Rwanda Franc", "SAR": "Saudi Riyal", "SBD": "Solomon Islands Dollar",
    "SCR": "Seychelles Rupee", "SDG": "Sudanese Pound", "SEK": "Swedish Krona",
    "SGD": "Singapore Dollar", "SHP": "Saint Helena Pound", "SLE": "Leone",
    "SOS": "Somali Shilling", "SRD": "Surinam Dollar", "SSP": "South Sudanese Pound",
    "STN": "Dobra", "SVC": "El Salvador Colon", "SYP": "Syrian Pound", "SZL": "Lilangeni",
    "THB": "Baht", "TJS": "Somoni", "TMT": "Turkmenistan New Manat", "TND": "Tunisian Dinar",
    "TOP": "Pa'anga", "TRY": "Turkish Lira", "TTD": "Trinidad and Tobago Dollar",
    "TWD": "New Taiwan Dollar", "TZS": "Tanzanian Shilling", "UAH": "Hryvnia",
    "UGX": "Uganda Shilling", "USD": "US Dollar", "UYU": "Peso Uruguayo",
    "UZS": "Uzbekistan Sum", "VES": "Bolívar Soberano", "VND": "Dong", "VUV": "Vatu",
    "WST": "Tala", "XAF": "CFA Franc BEAC", "XCD": "East Caribbean Dollar",
    "XOF": "CFA Franc BCEAO", "XPF": "CFP Franc", "YER": "Yemeni Rial", "ZAR": "Rand",
    "ZMW": "Zambian Kwacha", "ZWG": "Zimbabwe Gold",
}

# fmt: on


def slug_or_none(value: object, allowed: tuple[str, ...]) -> str | None:
    """Normalise a free-form value (e.g. "Full-time") to an allowed slug, or ``None``."""
    if not isinstance(value, str):
        return None
    slug = value.strip().lower().replace("-", "_").replace(" ", "_")
    return slug if slug in allowed else None
