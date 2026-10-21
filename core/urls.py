from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("administration/", views.administration, name="administration"),
    path("administration/site/<int:site_id>/autorisation/", views.site_approbation, name="site_approbation"),
    path("site-en-attente/", views.site_en_attente, name="site_en_attente"),
    path("changer-site/<int:site_id>/", views.changer_site, name="changer_site"),
]
