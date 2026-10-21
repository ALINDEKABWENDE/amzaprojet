from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("stock/", views.rapport_stock, name="rapport_stock"),
    path("stock/pdf/", views.rapport_stock_pdf, name="rapport_stock_pdf"),
    path("administration/", views.rapports_administration, name="rapports_administration"),
    path("administration/pdf/", views.rapports_administration_pdf, name="rapports_administration_pdf"),
    path("facture/<int:mouvement_id>/", views.facture_pdf, name="facture_pdf"),
    path("vente/<int:vente_id>/facture/", views.vente_pdf, name="vente_pdf"),
    path("vente/<int:vente_id>/recu/", views.vente_ticket_pdf, name="vente_ticket_pdf"),
    path("ticket/<int:transaction_id>/", views.ticket_pdf, name="ticket_pdf"),
    path("grand-livre/", views.grand_livre_pdf, name="grand_livre_pdf"),
    path("livre-caisse/", views.livre_caisse_pdf, name="livre_caisse_pdf"),
    path("fiche-produit/<int:produit_id>/", views.fiche_produit_pdf, name="fiche_produit_pdf"),
]
