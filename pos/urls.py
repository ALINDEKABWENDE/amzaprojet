from django.urls import path
from . import views

app_name = "pos"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("transaction/nouvelle/", views.nouvelle_transaction, name="nouvelle_transaction"),
    path("solde-operateur/approvisionner/", views.approvisionner_solde_operateur, name="approvisionner_solde_operateur"),
    path("transaction/<int:transaction_id>/modifier/", views.transaction_modifier, name="transaction_modifier"),
    path("historique/", views.historique, name="historique"),
]
