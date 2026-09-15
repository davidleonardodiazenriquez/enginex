"""Map catalog; readiness and provenance come from persisted portfolio records."""

from django.templatetags.static import static
from django.urls import reverse

from core.models import Asset

LOCATIONS = (
    {"id": "al-rayyana", "name": "Al Rayyana", "area": "Khalifa City",
     "coordinates": [24.4133, 54.5375], "category": "Residential community",
     "image": "al-rayyana.jpg", "description": "A neighbourhood of garden courtyards and connected living, beside Abu Dhabi Golf Club."},
    {"id": "gate", "name": "Gate", "area": "Al Reem Island",
     "coordinates": [24.4945, 54.4099], "category": "Residential towers",
     "image": "gate.png", "description": "An unmistakable silhouette on the skyline. Discover the Gate Towers in the heart of Shams Abu Dhabi."},
    {"id": "arc", "name": "Arc", "area": "Al Reem Island",
     "coordinates": [24.49525, 54.40965], "category": "Residential community",
     "image": "gate.png", "description": "A curved landmark within the Gate district, connecting city living with shared community spaces."},
    {"id": "the-bridges-ii", "name": "The Bridges II", "area": "Al Reem Island",
     "coordinates": [24.50885, 54.40598], "category": "Residential towers",
     "image": "the-bridges.jpg", "description": "Canals, parkland and the city meet in this contemporary neighbourhood on Al Reem Island."},
    {"id": "sas-al-nakhl", "name": "Sas Al Nakhl", "area": "Khalifa City",
     "coordinates": [24.40572, 54.52756], "category": "Villa community",
     "image": "sas-al-nakhl.jpg", "description": "A family neighbourhood of villas, green spaces and everyday community amenities."},
    {"id": "eastern-mangroves", "name": "Eastern Mangroves", "area": "Eastern Road",
     "coordinates": [24.4460, 54.4190], "category": "Waterfront community",
     "image": "eastern-mangroves.jpg", "description": "A waterfront address where the promenade meets Abu Dhabi’s natural mangroves."},
)


def map_locations():
    assets = {asset.name: asset for asset in Asset.objects.all()}
    locations = []
    for index, location in enumerate(LOCATIONS, 1):
        asset = assets.get(location["name"])
        ready = asset is not None
        locations.append({
            **location, "number": f"{index:02d}", "ready": ready,
            "image_url": static("core/locations/" + location["image"]),
            "metrics_url": (reverse("dashboard") if location["id"] == "al-rayyana" else reverse("asset_dashboard", args=[location["id"]])) if ready else None,
            "facts": [{"label": "Homes", "value": f"{asset.units:,}"},
                      {"label": "Buildings", "value": str(asset.buildings)}] if ready else [],
        })
    return locations
