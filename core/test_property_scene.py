from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, LeaseRecord
from core.property_scene import property_scene


class PropertySceneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_portfolio", verbosity=0)
        cls.user = get_user_model().objects.create_user(username="scene-viewer")

    def test_zone_metrics_and_report_match_only_that_assets_synthetic_unit_codes(self):
        asset = Asset.objects.get(name="Eastern Mangroves")
        # Similar-looking data from documents, other properties and invalid unit codes is excluded.
        LeaseRecord.objects.create(code="DOC-SCENE", asset=asset, origin="document", data={"unit_reference":"DEMO-06-B01-U900", "annual_rent":99999999, "occupancy_status":"Occupied"})
        LeaseRecord.objects.create(code="SYN-UNMAPPED", asset=asset, origin="synthetic", data={"unit_reference":"UNMAPPED-B01", "annual_rent":99999999})
        scene = property_scene(asset, "eastern-mangroves")
        self.assertEqual([z["records"] for z in scene["zones"]], [20] * 6)
        zone = scene["zones"][0]
        expected = [r.data for r in asset.lease_records.filter(origin="synthetic") if str(r.data.get("unit_reference", "")).startswith("DEMO-06-B01-")]
        occupied = [row for row in expected if row["occupancy_status"] == "Occupied"]
        self.assertEqual(zone["occupied"], len(occupied))
        self.assertEqual(float(zone["annual_rent"]), sum(row["annual_rent"] for row in occupied))
        self.client.force_login(self.user)
        response = self.client.get(zone["report_url"])
        self.assertEqual(response.context["page_obj"].paginator.count, 20)
        self.assertTrue(all(row["record"].asset_id == asset.pk for row in response.context["rows"]))
        self.assertContains(response, "Synthetic demo")
        self.assertNotContains(response, "DOC-SCENE")

    def test_all_six_assets_have_distinct_scene_config_and_no_geometry_claim(self):
        from core.locations import LOCATIONS
        self.client.force_login(self.user)
        for location in LOCATIONS:
            response = self.client.get(reverse("asset_dashboard", args=[location["id"]]))
            self.assertEqual(response.context["property_scene"]["slug"], location["id"])
            self.assertEqual(response.context["property_scene"]["name"], location["name"])
            self.assertContains(response, "ILLUSTRATIVE 3D MODEL")
            self.assertContains(response, "not a surveyed model")
            self.assertContains(response, "property-scene-loader.js")

    def test_empty_zones_have_no_invented_occupancy(self):
        asset = Asset.objects.get(name="Gate")
        asset.lease_records.all().delete()
        zones = property_scene(asset, "gate")["zones"]
        self.assertTrue(all(z["records"] == 0 and z["occupancy"] is None and z["annual_rent"] == "0" for z in zones))
