import uuid

from django.conf import settings
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
    field_sources = models.JSONField(default=dict, blank=True)

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


class LeaseRecord(models.Model):
    """A stable portfolio record. Baseline values are never replaced by extraction."""

    code = models.CharField(max_length=80, unique=True)
    asset = models.ForeignKey(Asset, null=True, blank=True, on_delete=models.PROTECT, related_name="lease_records")
    origin = models.CharField(max_length=20, choices=[("synthetic", "Synthetic demo"), ("document", "Document-backed")])
    data = models.JSONField(default=dict, blank=True)
    as_of = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.asset.name if self.asset else 'Unassigned location'}"


class ResidentFeedback(models.Model):
    """A recommendation response and its independently analyzed transcript."""

    reference = models.CharField(max_length=80, unique=True)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="resident_feedback")
    record = models.ForeignKey(LeaseRecord, null=True, blank=True, on_delete=models.SET_NULL)
    resident_name = models.CharField(max_length=120)
    received_on = models.DateField(db_index=True)
    channel = models.CharField(max_length=40, default="Resident interview")
    recommendation_score = models.PositiveSmallIntegerField(null=True, blank=True)
    transcript = models.TextField()
    origin = models.CharField(max_length=20, default="synthetic", choices=[("synthetic", "Generated"), ("resident", "Resident supplied")])
    source_metadata = models.JSONField(default=dict, blank=True)
    analysis_status = models.CharField(max_length=20, default="pending", db_index=True,
        choices=[("pending", "Awaiting analysis"), ("processing", "Analyzing"), ("completed", "Analyzed"), ("failed", "Needs analysis")])
    sentiment = models.CharField(max_length=20, blank=True,
        choices=[("positive", "Positive"), ("neutral", "Neutral"), ("negative", "Negative")])
    summary = models.TextField(blank=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    themes = models.JSONField(default=list, blank=True)
    analysis_model = models.CharField(max_length=100, blank=True)
    analysis_version = models.CharField(max_length=40, blank=True)
    analysis_input_hash = models.CharField(max_length=64, blank=True)
    analysis_started_at = models.DateTimeField(null=True, blank=True)
    analyzed_at = models.DateTimeField(null=True, blank=True)
    analysis_error = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-received_on", "reference"]
        constraints = [models.CheckConstraint(
            condition=models.Q(recommendation_score__isnull=True) | models.Q(recommendation_score__gte=0, recommendation_score__lte=10),
            name="feedback_recommendation_0_to_10",
        )]

    @property
    def nps_group(self):
        if self.recommendation_score is None:
            return "Unscored"
        return "Promoter" if self.recommendation_score >= 9 else "Passive" if self.recommendation_score >= 7 else "Detractor"


class ContractDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=240)
    sha256 = models.CharField(max_length=64, unique=True)
    storage_key = models.CharField(max_length=500)
    original_blob = models.CharField(max_length=1024, blank=True)
    size_bytes = models.PositiveIntegerField()
    page_count = models.PositiveIntegerField()
    source_label = models.CharField(max_length=100, default="Anonymized test contract")
    record = models.ForeignKey(LeaseRecord, on_delete=models.PROTECT, related_name="documents")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    association_status = models.CharField(max_length=20, default="pending", db_index=True, choices=[
        ("pending", "Awaiting extraction"), ("review", "Needs location review"),
        ("automatic", "Linked automatically"), ("manual", "Linked manually"),
        ("outside", "Reviewed · outside portfolio"),
    ])
    association_details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ExtractionRun(models.Model):
    document = models.ForeignKey(ContractDocument, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=20, default="queued", choices=[
        ("queued", "Queued"), ("running", "Extracting"), ("completed", "Ready for review"),
        ("failed", "Needs attention"),
    ])
    model = models.CharField(max_length=100, blank=True)
    pages = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["document"], condition=models.Q(status__in=["queued", "running"]), name="one_active_extraction_per_document")]


class ExtractedField(models.Model):
    run = models.ForeignKey(ExtractionRun, on_delete=models.CASCADE, related_name="fields")
    name = models.CharField(max_length=60)
    value = models.TextField()
    page = models.PositiveIntegerField()
    quote = models.TextField()
    review_status = models.CharField(max_length=15, default="pending", choices=[("pending", "Unreviewed extraction"), ("confirmed", "Reviewed extraction"), ("rejected", "Rejected")])
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["name", "page", "id"]


class AssociationEvent(models.Model):
    document = models.ForeignKey(ContractDocument, on_delete=models.CASCADE, related_name="associations")
    previous_record_code = models.CharField(max_length=80)
    record_code = models.CharField(max_length=80)
    location_name = models.CharField(max_length=120, blank=True)
    reason = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=20, default="manual", choices=[("manual", "Manual"), ("automatic", "Automatic")])
    evidence = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]
