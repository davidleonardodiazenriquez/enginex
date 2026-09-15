from django.contrib.auth import views as auth_views
from django.urls import path

from core.ai import views as ai_views
from core.ai.legacy import chat
from core.documents import views as documents
from core.forms import EnginexAuthenticationForm
from core.feedback import views as feedback
from core.portfolio.views import dashboard, portfolio_map
from core.process.views import process_workspace
from core.reports import views as reports
from core.views import health

urlpatterns = [
    path("process/", process_workspace, name="process"),
    path("feedback/", feedback.feedback_workspace, name="feedback"),
    path("feedback/<int:pk>/", feedback.feedback_detail, name="feedback_detail"),
    path("enginex-ai/", ai_views.workspace, name="enginex_ai"),
    path("api/enginex-ai/", ai_views.chat, name="enginex_ai_chat"),
    path("", portfolio_map, name="portfolio"),
    path("assets/al-rayyana/", dashboard, name="dashboard"),
    path("assets/<slug:asset_slug>/", dashboard, name="asset_dashboard"),
    path("reports/", reports.portfolio_report, name="portfolio_report"),
    path("reports/export/", reports.report_export, name="report_export"),
    path("records/<int:pk>/", reports.record_detail, name="record_detail"),
    path("contracts/", documents.contracts_workspace, name="contracts"),
    path("contracts/ingest/", documents.contract_ingest, name="contract_ingest"),
    path("contracts/<uuid:pk>/", documents.contract_detail, name="contract_detail"),
    path("contracts/<uuid:pk>/source/", documents.contract_source, name="contract_source"),
    path("contracts/<uuid:pk>/pages/<int:page>/", documents.contract_page, name="contract_page"),
    path("contracts/<uuid:pk>/extract/", documents.contract_extract, name="contract_extract"),
    path("contracts/<uuid:pk>/status/", documents.contract_status, name="contract_status"),
    path("contracts/<uuid:pk>/associate/", documents.contract_associate, name="contract_associate"),
    path("evidence/<int:pk>/review/", documents.field_review, name="field_review"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="core/login.html",
            authentication_form=EnginexAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("health/", health, name="health"),
    path("api/chat/", chat, name="chat"),
    path("api/assets/<slug:asset_slug>/chat/", chat, name="asset_chat"),
]
