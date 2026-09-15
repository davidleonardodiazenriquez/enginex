"""Shared resident-experience themes used by analysis, reports and AI queries."""

SENTIMENTS = ("positive", "neutral", "negative")
TOPICS = (
    "Maintenance", "Communication", "Parking", "Facilities",
    "Cleanliness", "Renewals", "Noise", "Security", "Landscaping",
)

TOPIC_PHRASES = {
    "Maintenance": ("air conditioning", "maintenance", "leaking tap", "technician", "repair"),
    "Communication": ("resident services", "community notices", "update", "messages"),
    "Parking": ("visitor parking", "parking ramp", "parking space", "parking permit", "parking"),
    "Facilities": ("swimming pool", "gym", "pool"),
    "Cleanliness": ("housekeeping", "waste collection", "corridors", "lift floors", "recycling"),
    "Renewals": ("lease renewal", "renewal", "leasing team"),
    "Noise": ("noise", "quiet", "peaceful", "daytime work"),
    "Security": ("security", "visitor access", "access card"),
    "Landscaping": ("landscaped", "landscaping", "gardens", "gardening", "garden lights", "irrigation", "walking paths"),
}
