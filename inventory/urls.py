from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("produits/", views.produits, name="produits"),
    path("vente/nouvelle/", views.nouvelle_vente, name="nouvelle_vente"),
    path("produit/<int:produit_id>/ajuster/", views.ajuster_stock, name="ajuster_stock"),
    path("produit/ajouter/", views.produit_ajouter, name="produit_ajouter"),
    path("produit/<int:produit_id>/modifier/", views.produit_modifier, name="produit_modifier"),
    path("produit/<int:produit_id>/supprimer/", views.produit_supprimer, name="produit_supprimer"),
    path("categorie/ajouter/", views.categorie_ajouter, name="categorie_ajouter"),
    path("historique/", views.historique, name="historique"),
]
