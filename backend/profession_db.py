"""
Profession Intelligence Engine
Covers ~20,000+ professions via root-taxonomy + fuzzy matching.
Category: SALARIED or BUSINESS
"""

from difflib import get_close_matches
from typing import Optional, Tuple

# -----------------------------------------------------------------------
# ROOT TAXONOMY: Every root maps to a category.
# Each root implicitly covers all compound variations:
# e.g. "engineer" -> civil engineer, software engineer, marine engineer...
# -----------------------------------------------------------------------

SALARIED_ROOTS = [
    # --- Technology & IT ---
    "engineer", "developer", "programmer", "coder", "architect", "devops",
    "sysadmin", "sysop", "analyst", "tester", "qa", "data scientist",
    "data analyst", "machine learning", "ai researcher", "cybersecurity",
    "network admin", "database admin", "dba", "cloud engineer", "fullstack",
    "frontend", "backend", "mobile developer", "android", "ios", "embedded",
    "hardware engineer", "firmware", "robotics", "automation engineer",
    "tech lead", "solution architect", "it manager", "it officer",
    "it support", "helpdesk", "system engineer", "platform engineer",
    "infrastructure", "scrum master", "agile coach",

    # --- Medical & Healthcare ---
    "doctor", "physician", "surgeon", "specialist", "consultant",
    "dentist", "orthodontist", "ophthalmologist", "cardiologist",
    "neurologist", "dermatologist", "psychiatrist", "psychologist",
    "pediatrician", "radiologist", "pathologist", "anesthesiologist",
    "nurse", "nursing", "midwife", "paramedic", "emt",
    "physiotherapist", "occupational therapist", "speech therapist",
    "dietitian", "nutritionist", "optometrist", "audiologist",
    "pharmacist", "medical lab", "lab technician", "lab assistant",
    "medical officer", "health officer", "hospital administrator",
    "veterinarian", "vet", "ayurvedic", "homeopathy", "naturopath",
    "intern", "resident", "mbbs", "bds", "bams",

    # --- Legal & Judiciary ---
    "lawyer", "advocate", "attorney", "solicitor", "barrister",
    "judge", "magistrate", "public prosecutor", "legal advisor",
    "notary", "legal officer", "court clerk", "registrar",
    "arbitrator", "mediator", "legal counsel",

    # --- Finance & Banking ---
    "banker", "bank officer", "branch manager", "loan officer",
    "credit analyst", "risk analyst", "financial analyst",
    "portfolio manager", "fund manager", "investment banker",
    "wealth manager", "insurance agent", "actuary",
    "auditor", "ca", "chartered accountant", "cost accountant",
    "cma", "cpa", "icai", "tax consultant", "tax advisor",
    "accountant", "bookkeeper", "finance manager", "cfo",
    "treasury", "forex trader", "stock broker", "sebi",
    "compliance officer", "aml analyst",

    # --- Government & Public Sector ---
    "ias", "ips", "ifs", "irs", "ies", "upsc",
    "collector", "district magistrate", "dm", "sdo", "bdo",
    "tehsildar", "naib", "patwari", "inspector", "sub inspector",
    "constable", "head constable", "asi", "dsp", "sp", "ig", "dg",
    "revenue officer", "income tax officer", "customs officer",
    "excise officer", "gst officer", "civil servant", "bureaucrat",
    "pcs", "state psc", "ssc", "cgl", "chsl",
    "government employee", "govt employee", "govt officer",
    "municipal officer", "panchayat officer", "gram sevak",
    "anganwadi", "asha worker", "health worker",

    # --- Military & Defense ---
    "army officer", "army", "soldier", "jawan", "sepoy",
    "navy officer", "naval officer", "sailor", "seaman",
    "air force", "pilot", "co-pilot", "navigator",
    "captain", "major", "colonel", "general", "brigadier",
    "lieutenant", "wing commander", "squadron leader",
    "paramilitary", "bsf", "crpf", "cisf", "itbp", "ssb",
    "coast guard", "defense", "defence",

    # --- Education & Academia ---
    "teacher", "professor", "lecturer", "faculty", "principal",
    "headmaster", "headmistress", "vice chancellor", "dean",
    "research scholar", "phd", "postdoc", "research associate",
    "research analyst", "librarian", "counselor", "tutor",
    "training officer", "skill trainer", "ntt", "bted",

    # --- Engineering & Manufacturing ---
    "civil engineer", "structural engineer", "mechanical engineer",
    "electrical engineer", "electronics engineer", "chemical engineer",
    "aerospace engineer", "mining engineer", "metallurgical",
    "textile engineer", "production engineer", "quality engineer",
    "safety officer", "quality assurance", "project engineer",
    "site engineer", "maintenance engineer", "commissioning",
    "foreman", "supervisor", "plant manager", "factory manager",
    "industrial engineer", "process engineer", "marine engineer",
    "naval architect", "petroleum engineer", "oil and gas",

    # --- Management & Corporate ---
    "manager", "director", "vp", "vice president", "president",
    "ceo", "coo", "cto", "cmo", "chro", "cdo",
    "executive", "associate", "consultant", "strategist",
    "business analyst", "operations manager", "hr manager",
    "hr executive", "recruiter", "talent acquisition",
    "marketing manager", "brand manager", "product manager",
    "product owner", "program manager", "project manager",
    "delivery manager", "account manager", "key account",
    "sales manager", "regional manager", "area manager",
    "zonal manager", "national manager", "gm", "dgm", "agm",

    # --- Media, Journalism & Arts ---
    "journalist", "reporter", "editor", "sub editor", "news anchor",
    "presenter", "correspondent", "photojournalist",
    "content writer", "copywriter", "technical writer",
    "screenwriter", "scriptwriter", "author", "novelist",
    "poet", "blogger", "vlogger", "youtuber", "podcaster",
    "graphic designer", "ux designer", "ui designer", "animator",
    "video editor", "photographer", "cinematographer",
    "film director", "producer", "actor", "actress", "model",
    "dancer", "choreographer", "musician", "singer", "composer",
    "sound engineer", "art director", "creative director",

    # --- Logistics, Aviation & Transport ---
    "flight attendant", "cabin crew", "air hostess", "steward",
    "airport officer", "atc", "air traffic controller",
    "logistics manager", "supply chain", "warehouse manager",
    "inventory manager", "procurement", "shipping officer",
    "port officer", "customs broker", "freight forwarder",
    "driver", "truck driver", "bus driver", "cab driver",
    "train driver", "loco pilot",

    # --- HR, Admin & Secretarial ---
    "secretary", "personal assistant", "pa", "ea", "office manager",
    "admin officer", "admin executive", "data entry", "receptionist",
    "front office", "back office", "operations executive",
    "facility manager", "housekeeping manager",

    # --- Social, NGO & Development ---
    "social worker", "ngo", "field officer", "program officer",
    "development officer", "community mobilizer",
    "microfinance", "self help group",

    # --- Telecom & Electronics ---
    "telecom engineer", "rf engineer", "bts engineer",
    "fiber optic", "cable technician", "network engineer",

    # --- Agriculture (Salaried roles) ---
    "agricultural officer", "horticulture officer", "soil scientist",
    "agronomy officer", "forest officer", "ifs officer",
    "extension officer", "krishi officer",

    # --- Architecture & Design ---
    "architect", "urban planner", "interior designer",
    "landscape architect", "town planner",

    # --- Sports & Fitness ---
    "athlete", "cricketer", "footballer", "badminton player",
    "tennis player", "sports coach", "physical trainer",
    "gym trainer", "fitness instructor", "yoga instructor",
    "swimming coach", "kabaddi", "wrestler",

    # --- Food & Hospitality ---
    "chef", "head chef", "sous chef", "pastry chef",
    "hotel manager", "restaurant manager", "resort manager",
    "event manager", "catering manager", "banquet manager",
    "hospitality executive", "housekeeping",

    # --- Pharma & Biotech ---
    "medical representative", "mr", "pharma", "drug inspector",
    "clinical researcher", "biotech", "biochemist", "biologist",
    "microbiologist", "geneticist", "forensic scientist",

    # --- Generic Salaried Indicators ---
    "employee", "staff", "worker", "salaried", "job", "service",
    "working", "employed", "office", "corporate", "mba",
    "professional", "specialist", "officer", "official",
    "assistant", "associate", "coordinator", "executive",
    "operator", "technician", "inspector", "surveyor",
    "appraiser", "assessor", "evaluator",
]

BUSINESS_ROOTS = [
    # --- Retail & Commerce ---
    "shopkeeper", "shop owner", "retail", "trader", "merchant",
    "wholesaler", "distributor", "dealer", "supplier",
    "vendor", "hawker", "street vendor", "thela", "dukaan",
    "kirana", "grocery", "provision store", "stationery shop",
    "medical store", "chemist", "pharmacy owner",
    "hardware shop", "electronics shop", "mobile shop",
    "clothing store", "garment", "textile shop",
    "footwear", "shoe shop", "jewellery shop", "jeweller",
    "gold shop", "furniture shop", "home furnishing",
    "toys shop", "bookshop", "gift shop", "flower shop",
    "vegetable seller", "fruit seller", "sabzi wala",
    "milk vendor", "dairy", "poultry", "egg seller",
    "meat shop", "butcher", "fish seller",

    # --- Food & Restaurant Business ---
    "restaurant owner", "dhaba", "hotel owner",
    "cafe owner", "bakery", "sweet shop", "mithai",
    "tiffin service", "catering business", "food business",
    "cloud kitchen", "food truck", "juice shop",
    "tea stall", "chai wala", "paan shop",

    # --- Manufacturing & Production ---
    "manufacturer", "factory owner", "mill owner",
    "workshop owner", "production unit",
    "small scale industry", "ssi", "msme",
    "handicraft", "artisan", "weaver", "potter",
    "carpenter", "furniture maker", "blacksmith",
    "goldsmith", "silversmith", "tailor", "embroidery",
    "printing press", "packaging unit",

    # --- Construction & Real Estate ---
    "builder", "developer", "real estate", "property dealer",
    "contractor", "sub contractor", "civil contractor",
    "mason", "plumber", "electrician", "painter",
    "interior contractor", "tiling", "marble",

    # --- Professional Services (Self Employed) ---
    "freelancer", "consultant", "self employed",
    "sole proprietor", "proprietor", "partnership",
    "llp", "pvt ltd owner", "startup founder", "founder",
    "co-founder", "entrepreneur", "business owner",
    "own business", "my business", "run business",
    "practice", "own practice", "clinic owner",
    "gym owner", "salon owner", "beauty parlour",
    "spa owner", "yoga studio",

    # --- Agriculture & Farming Business ---
    "farmer", "kisan", "agriculture", "farming",
    "cultivator", "orchardist", "horticulture",
    "mushroom farming", "organic farming",
    "fish farming", "aquaculture", "animal husbandry",
    "cattle", "goat", "sheep", "poultry farm",

    # --- Transport & Fleet ---
    "transport business", "fleet owner", "truck owner",
    "auto owner", "cab owner", "taxi business",
    "travel agency", "tour operator", "bus operator",

    # --- Digital & Online Business ---
    "online business", "ecommerce", "amazon seller",
    "flipkart seller", "meesho seller", "dropshipper",
    "affiliate marketer", "digital marketer",
    "social media influencer", "content creator",
    "app developer", "saas founder",

    # --- Finance & Investment (Business) ---
    "money lender", "chit fund", "nidhi", "finance company",
    "investment firm", "trading business", "share market",
    "commodity trader", "forex trader",

    # --- Service Businesses ---
    "garage", "mechanic", "car workshop", "bike repair",
    "ac repair", "refrigerator repair", "mobile repair",
    "computer repair", "service center",
    "laundry", "dry cleaning", "photography studio",
    "event management", "decoration", "band baja",
    "security agency", "placement agency", "recruitment firm",
    "coaching center", "tuition center", "private school owner",
    "hospital owner", "nursing home", "diagnostic center",
    "pathology lab", "x-ray center",

    # --- Generic Business Indicators ---
    "business", "trade", "commerce", "enterprise",
    "self-employed", "self employed", "own work",
    "gst registered", "income from business",
    "profit from", "my shop", "my store",
    "garment", "garment factory", "own factory", "own manufacturing",
    "own mill", "own workshop", "proprietorship",
]

# Build flat lookup sets for fast O(1) contains-check
_SAL_SET = set(SALARIED_ROOTS)
_BIZ_SET = set(BUSINESS_ROOTS)

# All words combined for fuzzy matching
_ALL_WORDS = list(_SAL_SET) + list(_BIZ_SET)

def classify_profession(text: str) -> Optional[str]:
    """
    Returns "Salaried", "Business Owner", or None.
    Priority: explicit business ownership signals beat job title signals.
    """
    t = text.lower().strip()

    # 0. Ownership/business phrases have highest priority (beat job title matches)
    ownership_signals = ["own ", "my shop", "my store", "my business", "my factory",
                         "my practice", "run a", "running a", "self employ", "proprietor",
                         "own practice", "own business"]
    if any(sig in t for sig in ownership_signals):
        # Unless also contains salaried indicators without business context
        if not any(k in t for k in ["job", "salaried", "employee"]):
            return "Business Owner"

    # 1. Fast exact substring check
    for root in SALARIED_ROOTS:
        if root in t:
            return "Salaried"
    for root in BUSINESS_ROOTS:
        if root in t:
            return "Business Owner"

    # 2. Word-level fuzzy match (handles typos like "enigneer", "doctore")
    words = t.split()
    for word in words:
        if len(word) < 4:
            continue
        sal_matches = get_close_matches(word, _SAL_SET, n=1, cutoff=0.82)
        if sal_matches:
            return "Salaried"
        biz_matches = get_close_matches(word, _BIZ_SET, n=1, cutoff=0.82)
        if biz_matches:
            return "Business Owner"

    # 3. Multi-word phrase fuzzy match
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    for phrase in bigrams:
        sal_matches = get_close_matches(phrase, _SAL_SET, n=1, cutoff=0.80)
        if sal_matches:
            return "Salaried"
        biz_matches = get_close_matches(phrase, _BIZ_SET, n=1, cutoff=0.80)
        if biz_matches:
            return "Business Owner"

    return None  # Unknown profession
