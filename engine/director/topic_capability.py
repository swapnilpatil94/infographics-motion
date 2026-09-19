"""Topic capability registry for deterministic shot planning."""
from dataclasses import dataclass, field
from typing import Dict, List, Set

@dataclass(frozen=True)
class TopicProfile:
    id: str
    family: str
    visual_modes: Set[str]
    reusable_assets: Set[str] = field(default_factory=set)
    specialist_assets: Set[str] = field(default_factory=set)
    notes: str = ""

PROFILES: Dict[str, TopicProfile] = {
    "money_behavior": TopicProfile(
        "money_behavior", "money_psychology",
        {"character", "environment", "prop", "infographic"},
        {"person","phone","laptop","cash","card","bank_app","home","office","graph","numbers"},
        {"specific_bank_brand","specific_financial_institution","historical_currency"},
        "Strong fit for human behavior, transactions, incentives and financial mechanisms.",
    ),
    "technology_internet": TopicProfile(
        "technology_internet", "technology",
        {"character","environment","prop","infographic","network"},
        {"person","phone","laptop","server","router","chat","browser","network_graph","numbers"},
        {"specific_product_ui","specific_hardware","brand_logo"},
        "Strong fit for mechanisms and human stories; exact products need registered reference assets.",
    ),
    "human_behavior": TopicProfile(
        "human_behavior", "psychology",
        {"character","environment","prop","infographic"},
        {"person","home","office","phone","shopping","clock","graph","text"},
        {"lab_equipment","clinical_environment"},
        "Strong fit for everyday human situations and visual metaphors.",
    ),
    "history": TopicProfile(
        "history", "history",
        {"character","environment","prop","map","timeline","infographic"},
        {"person","map","document","timeline","generic_building","generic_vehicle"},
        {"period_costume","period_architecture","specific_artifact","specific_vehicle","crowd"},
        "Viable when historical specificity is represented by a curated asset pack.",
    ),
    "mythology": TopicProfile(
        "mythology", "mythology",
        {"character","environment","prop","symbol","infographic"},
        {"human_figure","temple","forest","mountain","fire","ornament","symbol"},
        {"deity_character","specific_costume","specific_weapon","specific_temple","animal_mount"},
        "Requires a deliberate mythology asset library and provenance ledger.",
    ),
    "business_power": TopicProfile(
        "business_power", "business",
        {"character","environment","prop","infographic","network"},
        {"person","office","phone","laptop","document","money","graph","network_graph"},
        {"company_logo","specific_product","specific_factory","specific_person"},
        "Strong fit for incentives, competition and consumer behavior.",
    ),
    "science_explainer": TopicProfile(
        "science_explainer", "science",
        {"infographic","diagram","timeline","map","character"},
        {"diagram","graph","molecule","cell","planet","timeline","numbers"},
        {"specific_instrument","specific_species","specific_structure"},
        "Best when the explanation can be expressed with controlled diagrams and metaphors.",
    ),
}

def get_profile(topic_family: str) -> TopicProfile:
    key = topic_family.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in PROFILES:
        raise KeyError(f"Unsupported topic family: {topic_family}")
    return PROFILES[key]

def capability_report(topic_family: str, requested_assets: List[str]) -> dict:
    profile = get_profile(topic_family)
    requested = {a.strip().lower() for a in requested_assets}
    missing = sorted(requested - profile.reusable_assets)
    specialist = sorted(requested & profile.specialist_assets)
    return {
        "topic_family": profile.family,
        "supported_visual_modes": sorted(profile.visual_modes),
        "requested_assets": sorted(requested),
        "missing_from_reusable_pack": missing,
        "specialist_assets": specialist,
        "compile": not specialist and not missing,
        "notes": profile.notes,
    }
