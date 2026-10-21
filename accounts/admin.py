
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "telephone", "profil", "site_actif", "is_staff")
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Informations métier", {"fields": ("telephone", "profil")}),
    )
    fieldsets = UserAdmin.fieldsets + (
        ("Informations métier", {"fields": ("telephone", "profil", "sites", "site_actif")}),
    )