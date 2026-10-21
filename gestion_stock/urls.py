from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="accounts:redirect", permanent=False)),
    path("admin/", admin.site.urls),
    path("comptes/", include("accounts.urls")),
    path("quincaillerie/", include("inventory.urls")),
    path("shop/", include("pos.urls")),
    path("rapports/", include("reports.urls")),
    path("site/", include("core.urls")),
]
