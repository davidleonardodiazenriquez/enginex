from django.db import models


class Asset(models.Model):
    name = models.CharField(max_length=120, unique=True)
    location = models.CharField(max_length=180)
    asset_class = models.CharField(max_length=120)
    developer = models.CharField(max_length=120)
    buildings = models.PositiveIntegerField()
    units = models.PositiveIntegerField()
    unit_mix = models.CharField(max_length=160)
    amenities = models.TextField()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TenantRevenue(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="tenant_revenues")
    rank = models.PositiveSmallIntegerField()
    tenant_name = models.CharField(max_length=120)
    revenue_share = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["asset", "rank"], name="unique_asset_tenant_rank")
        ]

    def __str__(self):
        return f"{self.asset}: {self.tenant_name}"


class Vacancy(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="vacancies")
    rank = models.PositiveSmallIntegerField()
    unit_name = models.CharField(max_length=120)
    revenue_share = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["asset", "rank"], name="unique_asset_vacancy_rank")
        ]

    def __str__(self):
        return f"{self.asset}: {self.unit_name}"


class PortfolioMetrics(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name="metrics")
    due_completed_pct = models.DecimalField(max_digits=5, decimal_places=2)
    due_completed_value = models.DecimalField(max_digits=12, decimal_places=2)
    due_incomplete_value = models.DecimalField(max_digits=12, decimal_places=2)
    upcoming_signed_pct = models.DecimalField(max_digits=5, decimal_places=2)
    upcoming_signed_value = models.DecimalField(max_digits=12, decimal_places=2)
    upcoming_unsigned_value = models.DecimalField(max_digits=12, decimal_places=2)
    reversionary_pct = models.DecimalField(max_digits=5, decimal_places=2)
    in_place_rent = models.DecimalField(max_digits=12, decimal_places=2)
    market_rent = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name_plural = "portfolio metrics"

    @property
    def total_due(self):
        return self.due_completed_value + self.due_incomplete_value

    @property
    def total_upcoming(self):
        return self.upcoming_signed_value + self.upcoming_unsigned_value

    @property
    def potential_upside(self):
        return self.market_rent - self.in_place_rent

    def __str__(self):
        return f"Metrics for {self.asset}"
