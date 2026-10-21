from django.contrib import admin
from .models import Caisse, SoldeOperateur, TransactionMobileMoney


@admin.register(Caisse)
class CaisseAdmin(admin.ModelAdmin):
    list_display = ("site", "solde", "derniere_maj")


@admin.register(SoldeOperateur)
class SoldeOperateurAdmin(admin.ModelAdmin):
    list_display = ("site", "operateur", "operateur_autre", "devise", "solde", "derniere_maj")
    list_filter = ("site", "operateur", "devise")
    search_fields = ("operateur_autre", "site__nom")


@admin.register(TransactionMobileMoney)
class TransactionMobileMoneyAdmin(admin.ModelAdmin):
    list_display = ("site", "type_transaction", "client_nom", "montant", "agent", "date_transaction")
    list_filter = ("site", "type_transaction", "date_transaction")
    search_fields = ("client_nom", "client_telephone")
