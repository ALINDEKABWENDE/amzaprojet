from django.contrib import admin
from .models import Categorie, Produit, MouvementStock


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "site")
    list_filter = ("site",)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ("nom", "categorie", "site", "quantite_stock", "prix_vente", "en_alerte")
    list_filter = ("site", "categorie")
    search_fields = ("nom", "reference")


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ("produit", "type_mouvement", "quantite", "utilisateur", "date_mouvement")
    list_filter = ("type_mouvement", "date_mouvement")
