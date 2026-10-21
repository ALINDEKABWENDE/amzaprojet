from django.contrib import admin
from .models import Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("nom", "type_site", "ville", "actif", "date_creation")
    list_filter = ("actif", "type_site", "ville")
    search_fields = ("nom", "ville", "adresse")
    ordering = ("actif", "nom")
    list_per_page = 25
