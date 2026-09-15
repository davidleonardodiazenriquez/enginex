from django.contrib import admin

from core.models import (
    Asset,
    AssociationEvent,
    ContractDocument,
    ExtractedField,
    ExtractionRun,
    LeaseRecord,
    PortfolioMetrics,
    ResidentFeedback,
    TenantRevenue,
    Vacancy,
)

admin.site.register(Asset)
admin.site.register(TenantRevenue)
admin.site.register(Vacancy)
admin.site.register(PortfolioMetrics)
admin.site.register([LeaseRecord, ContractDocument, ExtractionRun, ExtractedField, AssociationEvent])


@admin.register(ResidentFeedback)
class ResidentFeedbackAdmin(admin.ModelAdmin):
    list_display = ("reference", "asset", "resident_name", "recommendation_score", "sentiment", "analysis_status")
    list_filter = ("asset", "sentiment", "analysis_status")
    search_fields = ("reference", "resident_name", "transcript")
    readonly_fields = ("summary", "sentiment", "sentiment_score", "keywords", "themes", "analysis_status",
                       "analysis_model", "analysis_version", "analysis_input_hash", "analyzed_at", "analysis_error", "analysis_started_at")

    def save_model(self, request, obj, form, change):
        if not change or "transcript" in form.changed_data:
            obj.analysis_status = "pending"
            obj.sentiment = obj.summary = obj.analysis_error = ""
            obj.sentiment_score = obj.analyzed_at = None
            obj.keywords, obj.themes = [], []
        super().save_model(request, obj, form, change)
