from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Site
from .models import SoldeOperateur, TransactionMobileMoney


class DashboardStatisticsTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(nom="Shop Test", type_site="shop", actif=True)
        self.user = get_user_model().objects.create_user(
            username="caissier",
            password="test-password",
            telephone="0999000002",
            profil="shop",
            site_actif=self.site,
        )
        self.user.sites.add(self.site)
        self.client.force_login(self.user)

        TransactionMobileMoney.objects.create(
            site=self.site,
            agent=self.user,
            type_transaction="depot",
            operateur="mpesa",
            client_nom="Client dépôt",
            client_telephone="0999111111",
            montant=Decimal("250.00"),
            frais=Decimal("15.00"),
        )
        TransactionMobileMoney.objects.create(
            site=self.site,
            agent=self.user,
            type_transaction="retrait",
            operateur="airtel_money",
            client_nom="Client retrait",
            client_telephone="0999222222",
            montant=Decimal("80.00"),
            frais=Decimal("8.00"),
        )

    def test_shop_navigation_uses_the_shared_responsive_header(self):
        response = self.client.get(reverse("pos:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "navbar-expand-xl")
        self.assertContains(response, "app-navbar")
        self.assertNotContains(response, "hardware-navbar")
        self.assertContains(response, "Tableau de bord")
        self.assertContains(response, "Historique")

    def test_dashboard_displays_period_and_operator_filtered_charts(self):
        ancienne_transaction = TransactionMobileMoney.objects.create(
            site=self.site,
            agent=self.user,
            type_transaction="depot",
            operateur="mpesa",
            client_nom="Ancienne transaction",
            client_telephone="0999333333",
            montant=Decimal("100.00"),
            frais=Decimal("50.00"),
        )
        TransactionMobileMoney.objects.filter(pk=ancienne_transaction.pk).update(
            date_transaction=timezone.now() - timedelta(days=2)
        )

        today = timezone.localdate().isoformat()
        response = self.client.get(
            reverse("pos:dashboard"),
            {"operateur": "mpesa", "devise": "USD", "debut": today, "fin": today},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_depots"], Decimal("250.00"))
        self.assertEqual(response.context["total_retraits"], 0)
        self.assertEqual(response.context["nombre_transactions"], 1)
        self.assertEqual(response.context["benefice"], Decimal("15.00"))
        self.assertEqual(response.context["depots_par_jour"], [250.0])
        self.assertEqual(response.context["retraits_par_jour"], [0.0])
        self.assertIn("operateur=mpesa", response.context["report_querystring"])
        self.assertIn("devise=USD", response.context["report_querystring"])
        self.assertIn("debut=" + today, response.context["report_querystring"])
        self.assertIn("fin=" + today, response.context["report_querystring"])
        self.assertContains(response, "Bénéfice (frais)")
        self.assertContains(response, "250,00 USD")
        self.assertContains(response, "15,00 USD")
        self.assertContains(response, "250,00</td>")
        self.assertContains(response, 'id="cashTypeChart"')
        self.assertContains(response, 'id="cashActivityChart"')

    def test_dashboard_transactions_are_paginated_and_keep_filters(self):
        for number in range(10):
            TransactionMobileMoney.objects.create(
                site=self.site,
                agent=self.user,
                type_transaction="depot",
                operateur="mpesa",
                client_nom=f"Client supplémentaire {number}",
                client_telephone=f"09993333{number:02d}",
                montant=Decimal("10.00"),
            )

        today = timezone.localdate().isoformat()
        url = reverse("pos:dashboard")
        params = {"operateur": "mpesa", "debut": today, "fin": today, "page_size": 10}
        first_page = self.client.get(url, params)
        second_page = self.client.get(url, {**params, "page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["transactions"].paginator.count, 11)
        self.assertEqual(len(first_page.context["transactions"]), 10)
        self.assertContains(first_page, "10,00")
        self.assertContains(first_page, "Affichage")
        self.assertContains(first_page, "page=2#transactions")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.context["transactions"].number, 2)
        self.assertEqual(len(second_page.context["transactions"]), 1)
        self.assertEqual(second_page.context["transactions"].object_list[0].operateur, "mpesa")
        self.assertContains(second_page, "operateur=mpesa")
        self.assertContains(second_page, "debut=" + today)
        self.assertEqual(second_page.context["page_size"], 10)

    def test_dashboard_allows_more_transactions_per_page(self):
        for number in range(11):
            TransactionMobileMoney.objects.create(
                site=self.site,
                agent=self.user,
                type_transaction="depot",
                operateur="mpesa",
                client_nom=f"Client pagination {number}",
                client_telephone=f"09996666{number:02d}",
                montant=Decimal("5.00"),
            )

        today = timezone.localdate().isoformat()
        response = self.client.get(
            reverse("pos:dashboard"),
            {
                "operateur": "mpesa",
                "debut": today,
                "fin": today,
                "page_size": 25,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_size"], 25)
        self.assertEqual(response.context["transactions"].paginator.per_page, 25)
        self.assertEqual(len(response.context["transactions"]), 12)
        self.assertContains(response, 'id="transactionPageSize"')
        self.assertContains(response, "25")

    def test_dashboard_filters_and_totals_keep_currencies_separate(self):
        TransactionMobileMoney.objects.create(
            site=self.site,
            agent=self.user,
            type_transaction="depot",
            operateur="mpesa",
            client_nom="Client CDF",
            client_telephone="0999555555",
            montant=Decimal("50000.00"),
            frais=Decimal("1000.00"),
            devise="CDF",
        )

        today = timezone.localdate().isoformat()
        response = self.client.get(
            reverse("pos:dashboard"),
            {"devise": "CDF", "debut": today, "fin": today},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_depots"], Decimal("0"))
        self.assertEqual(response.context["total_depots_cdf"], Decimal("50000.00"))
        self.assertEqual(response.context["benefice_cdf"], Decimal("1000.00"))
        self.assertEqual(response.context["nombre_transactions"], 1)
        self.assertContains(response, "Franc congolais (CDF)")

    def test_cdf_transaction_uses_a_separate_cash_balance(self):
        SoldeOperateur.objects.create(
            site=self.site,
            operateur="mpesa",
            devise="CDF",
            solde=Decimal("50000.00"),
        )
        response = self.client.post(
            reverse("pos:nouvelle_transaction"),
            {
                "type_transaction": "depot",
                "operateur": "mpesa",
                "client_nom": "Client CDF",
                "client_telephone": "0999555555",
                "devise": "CDF",
                "montant": "50000.00",
                "frais": "1000.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("pos:dashboard"))
        caisse = self.site.caisse
        self.assertEqual(caisse.solde, Decimal("0.00"))
        self.assertEqual(caisse.solde_cdf, Decimal("-50000.00"))
        transaction = TransactionMobileMoney.objects.get(client_nom="Client CDF")
        self.assertEqual(transaction.devise, "CDF")
        solde = SoldeOperateur.objects.get(site=self.site, operateur="mpesa", devise="CDF")
        self.assertEqual(solde.solde, Decimal("0.00"))

    def test_deposit_reduces_available_operator_float(self):
        SoldeOperateur.objects.create(
            site=self.site,
            operateur="mpesa",
            devise="USD",
            solde=Decimal("100.00"),
        )

        response = self.client.post(
            reverse("pos:nouvelle_transaction"),
            {
                "type_transaction": "depot",
                "operateur": "mpesa",
                "client_nom": "Dépôt couvert",
                "client_telephone": "0999555667",
                "devise": "USD",
                "montant": "75.00",
                "frais": "3.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TransactionMobileMoney.objects.filter(client_nom="Dépôt couvert").exists())
        solde = SoldeOperateur.objects.get(site=self.site, operateur="mpesa", devise="USD")
        self.assertEqual(solde.solde, Decimal("25.00"))

    def test_deposit_is_rejected_when_operator_float_is_insufficient(self):
        SoldeOperateur.objects.create(
            site=self.site,
            operateur="mpesa",
            devise="USD",
            solde=Decimal("20.00"),
        )

        response = self.client.post(
            reverse("pos:nouvelle_transaction"),
            {
                "type_transaction": "depot",
                "operateur": "mpesa",
                "client_nom": "Dépôt impossible",
                "client_telephone": "0999555668",
                "devise": "USD",
                "montant": "75.00",
                "frais": "3.00",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TransactionMobileMoney.objects.filter(client_nom="Dépôt impossible").exists())
        solde = SoldeOperateur.objects.get(site=self.site, operateur="mpesa", devise="USD")
        self.assertEqual(solde.solde, Decimal("20.00"))
        self.assertContains(response, "Solde virtuel insuffisant")
        self.assertContains(response, "20.00 disponible")

    def test_operator_float_can_be_initialized_and_replenished(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        url = reverse("pos:approvisionner_solde_operateur")
        data = {
            "operateur": "autre_mobile",
            "operateur_autre": "Nita Money",
            "devise": "CDF",
            "montant": "75000.00",
        }

        first_response = self.client.post(url, data)
        self.assertEqual(first_response.status_code, 302)
        balance = SoldeOperateur.objects.get(
            site=self.site,
            operateur="autre_mobile",
            operateur_autre="Nita Money",
            devise="CDF",
        )
        self.assertEqual(balance.solde, Decimal("75000.00"))

        self.client.post(url, {**data, "montant": "25000.00"})
        balance.refresh_from_db()
        self.assertEqual(balance.solde, Decimal("100000.00"))

    def test_non_staff_cannot_replenish_operator_float(self):
        response = self.client.post(
            reverse("pos:approvisionner_solde_operateur"),
            {
                "operateur": "mpesa",
                "devise": "USD",
                "montant": "100.00",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SoldeOperateur.objects.filter(site=self.site).exists())
        self.assertContains(response, "Seul un administrateur")

    def test_withdrawal_credits_virtual_operator_balance(self):
        response = self.client.post(
            reverse("pos:nouvelle_transaction"),
            {
                "type_transaction": "retrait",
                "operateur": "airtel_money",
                "client_nom": "Retrait crédité",
                "client_telephone": "0999555669",
                "devise": "CDF",
                "montant": "25000.00",
                "frais": "500.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        solde = SoldeOperateur.objects.get(
            site=self.site,
            operateur="airtel_money",
            devise="CDF",
        )
        self.assertEqual(solde.solde, Decimal("25000.00"))

    def test_transaction_edit_does_not_allow_balance_affecting_changes(self):
        transaction = TransactionMobileMoney.objects.get(client_nom="Client dépôt")

        response = self.client.post(
            reverse("pos:transaction_modifier", args=[transaction.id]),
            {
                "client_nom": "Client corrigé",
                "client_telephone": "0999000003",
                "frais": "12.00",
                "montant": "999999.00",
                "devise": "CDF",
                "operateur": "airtel_money",
                "type_transaction": "retrait",
            },
        )

        self.assertEqual(response.status_code, 302)
        transaction.refresh_from_db()
        self.assertEqual(transaction.client_nom, "Client corrigé")
        self.assertEqual(transaction.montant, Decimal("250.00"))
        self.assertEqual(transaction.devise, "USD")
        self.assertEqual(transaction.operateur, "mpesa")
        self.assertEqual(transaction.type_transaction, "depot")

    def test_dashboard_refresh_after_transaction_shows_updated_totals(self):
        response = self.client.post(
            reverse("pos:nouvelle_transaction"),
            {
                "type_transaction": "retrait",
                "operateur": "mpesa",
                "client_nom": "Client actualisé",
                "client_telephone": "0999555666",
                "devise": "USD",
                "montant": "25.00",
                "frais": "2.50",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(reverse("pos:dashboard"), 302)])
        self.assertEqual(response.context["total_retraits"], Decimal("105.00"))
        self.assertEqual(response.context["benefice"], Decimal("25.50"))
        self.assertContains(response, "Client actualisé")
        self.assertContains(response, "Transaction enregistrée avec succès.")

    def test_history_transactions_are_paginated_and_keep_all_filters(self):
        for number in range(10):
            TransactionMobileMoney.objects.create(
                site=self.site,
                agent=self.user,
                type_transaction="depot",
                operateur="mpesa",
                client_nom=f"Client dépôt supplémentaire {number}",
                client_telephone=f"09994444{number:02d}",
                montant=Decimal("10.00"),
            )

        today = timezone.localdate().isoformat()
        url = reverse("pos:historique")
        filters = {
            "type": "depot",
            "operateur": "mpesa",
            "debut": today,
            "fin": today,
            "q": "Client",
        }
        first_page = self.client.get(url, filters)
        second_page = self.client.get(url, {**filters, "page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["transactions"].paginator.count, 11)
        self.assertEqual(len(first_page.context["transactions"]), 10)
        self.assertContains(first_page, "Affichage")
        self.assertContains(first_page, "page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.context["transactions"].number, 2)
        self.assertEqual(len(second_page.context["transactions"]), 1)
        self.assertContains(second_page, "type=depot")
        self.assertContains(second_page, "operateur=mpesa")
        self.assertContains(second_page, "debut=" + today)
        self.assertContains(second_page, "fin=" + today)
        self.assertContains(second_page, "q=Client")
        self.assertContains(first_page, "Rapport filtré (PDF)")

    def test_history_filters_and_summarizes_each_currency_separately(self):
        TransactionMobileMoney.objects.create(
            site=self.site,
            agent=self.user,
            type_transaction="depot",
            operateur="mpesa",
            client_nom="Client CDF",
            client_telephone="0999555555",
            montant=Decimal("50000.00"),
            devise="CDF",
        )

        response = self.client.get(
            reverse("pos:historique"),
            {"devise": "CDF"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(
            response.context["totaux_par_devise"]["CDF"]["depot"],
            Decimal("50000.00"),
        )
        self.assertEqual(response.context["filtres"]["devise"], "CDF")
