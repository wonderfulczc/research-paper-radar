import re


S_TIER_VENUES = [
    "Nature",
    "Science",
    "Nature Electronics",
    "Nature Sensors",
    "Nature Communications",
    "Nature Nanotechnology",
    "Nature Materials",
    "Science Advances",
    "Science Robotics",
    "PNAS",
    "Proceedings of the National Academy of Sciences",
    "Device",
    "Matter",
]

A_TIER_VENUES = [
    "Nano Energy",
    "Advanced Materials",
    "Advanced Functional Materials",
    "Advanced Science",
    "Advanced Energy Materials",
    "ACS Nano",
    "Nano Letters",
    "ACS Sensors",
    "Small Methods",
    "Microsystems & Nanoengineering",
    "npj Flexible Electronics",
    "Sensors and Actuators A: Physical",
    "Smart Materials and Structures",
]

IEEE_CORE_VENUES = [
    "IEEE Transactions on Electron Devices",
    "IEEE Transactions on Instrumentation and Measurement",
    "IEEE Transactions on Dielectrics and Electrical Insulation",
    "IEEE Transactions on Antennas and Propagation",
    "IEEE Transactions on Microwave Theory and Techniques",
    "IEEE Transactions on Wireless Communications",
    "IEEE Transactions on Industrial Electronics",
    "IEEE Transactions on Industrial Informatics",
    "IEEE Transactions on Circuits and Systems I: Regular Papers",
    "IEEE Transactions on Circuits and Systems II: Express Briefs",
    "IEEE Transactions on Biomedical Circuits and Systems",
    "IEEE Sensors Journal",
    "IEEE Sensors Letters",
    "IEEE Internet of Things Journal",
    "IEEE Journal on Flexible Electronics",
    "IEEE Transactions on Plasma Science",
]

B_TIER_DIRECT_ONLY_VENUES = [
    "Energy & Environmental Science",
    "Joule",
    "Materials Today",
    "Advanced Electronic Materials",
    "Advanced Intelligent Systems",
    "Advanced Sensor Research",
    "Lab on a Chip",
    "Flexible and Printed Electronics",
    "Measurement Science and Technology",
    "Sensors and Actuators B: Chemical",
]

VENUE_PRIORITY_RANK = {
    "S": 4,
    "IEEE": 3,
    "A": 2,
    "B": 1,
    "ordinary": 0,
}


def normalize_venue_name(value: str) -> str:
    value = (value or "").lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _matches(venue: str, names: list[str]) -> bool:
    normalized = normalize_venue_name(venue)
    if not normalized:
        return False
    for name in names:
        target = normalize_venue_name(name)
        if normalized == target:
            return True
    return False


def venue_priority(venue: str) -> str:
    if _matches(venue, S_TIER_VENUES):
        return "S"
    if _matches(venue, IEEE_CORE_VENUES):
        return "IEEE"
    if _matches(venue, A_TIER_VENUES):
        return "A"
    if _matches(venue, B_TIER_DIRECT_ONLY_VENUES):
        return "B"
    return "ordinary"


def venue_priority_rank(venue_or_priority: str) -> int:
    priority = venue_or_priority
    if priority not in VENUE_PRIORITY_RANK:
        priority = venue_priority(venue_or_priority)
    return VENUE_PRIORITY_RANK.get(priority, 0)


def venue_priority_label(priority: str) -> str:
    return {
        "S": "S级顶刊/大子刊优先",
        "A": "A级强相关期刊优先",
        "IEEE": "IEEE核心优先",
        "B": "B级直接机制候选",
        "ordinary": "普通/未知venue",
    }.get(priority or "ordinary", "普通/未知venue")


def is_priority_venue(venue: str) -> bool:
    return venue_priority(venue) in {"S", "A", "IEEE"}


def is_watch_venue(venue: str) -> bool:
    return venue_priority(venue) == "B"


def is_ac_exception_venue(venue: str) -> bool:
    priority = venue_priority(venue)
    return priority == "S" or normalize_venue_name(venue).startswith("ieee transactions")
