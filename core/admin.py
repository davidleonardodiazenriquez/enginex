from django.contrib import admin

from core.models import Asset, PortfolioMetrics, TenantRevenue, Vacancy, LeaseRecord, ContractDocument, ExtractionRun, ExtractedField, AssociationEvent

admin.site.register(Asset)
admin.site.register(TenantRevenue)
admin.site.register(Vacancy)
admin.site.register(PortfolioMetrics)
admin.site.register([LeaseRecord, ContractDocument, ExtractionRun, ExtractedField, AssociationEvent])
