from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from inventory.models import Categorie, MouvementStock, Produit
from core.models import Site
from pos.models import TransactionMobileMoney
from .pdf_utils import render_pdf


class CompanyPdfHeaderTests(SimpleTestCase):
    def test_shared_company_header_shows_registered_business_details(self):
        site = Site(
            nom="Quincaillerie du Marché",
            type_site="quincaillerie",
            adresse="12 avenue du Commerce",
            ville="Kinshasa",
        )

        html = render_to_string(
            "reports/partials/entete_entreprise.html",
            {
                "site": site,
                "entete_document": "FACTURE",
                "reference_document": 42,
                "date_document": timezone.now(),
            },
        )

        self.assertIn("Quincaillerie du Marché", html)
        self.assertIn("Quincaillerie", html)
        self.assertIn("12 avenue du Commerce", html)
        self.assertIn("Kinshasa", html)
        self.assertIn("FACTURE", html)
        self.assertIn("42", html)

    def test_all_pdf_templates_render_the_company_header(self):
        site = Site(
            nom="Shop Central",
            type_site="shop",
            adresse="5 rue Principale",
            ville="Goma",
        )
        now = timezone.now()
        templates = (
            "reports/facture.html",
            "reports/facture_vente.html",
            "reports/ticket_vente_thermique.html",
            "reports/ticket_thermique.html",
            "reports/grand_livre.html",
            "reports/rapport_stock_pdf.html",
            "reports/livre_caisse.html",
            "reports/fiche_produit.html",
        )

        for template_name in templates:
            with self.subTest(template=template_name):
                html = render_to_string(
                    template_name,
                    {
                        "site": site,
                        "date_emission": now,
                        "date_generation": now,
                        "date_document": now,
                        "entete_document": "DOCUMENT",
                        "reference_document": 1,
                    },
                )
                self.assertIn("Shop Central", html)
                self.assertIn("5 rue Principale", html)
                self.assertIn("Goma", html)

    def test_multi_page_pdf_templates_repeat_header_and_footer(self):
        templates = (
            "reports/facture.html",
            "reports/facture_vente.html",
            "reports/grand_livre.html",
            "reports/rapport_stock_pdf.html",
            "reports/livre_caisse.html",
            "reports/fiche_produit.html",
        )

        for template_name in templates:
            with self.subTest(template=template_name):
                html = render_to_string(
                    template_name,
                    {
                        "site": Site(nom="Shop Central", type_site="shop"),
                        "mouvement": None,
                        "vente": None,
                        "produit": type("Produit", (), {"reference": "", "nom": "Article"})(),
                        "lignes": [],
                        "mouvements": [],
                        "transactions": [],
                        "date_emission": timezone.now(),
                        "date_generation": timezone.now(),
                        "date_document": timezone.now(),
                        "entete_document": "DOCUMENT",
                        "reference_document": 1,
                        "debut": None,
                        "fin": None,
                        "total": 0,
                        "chiffre_affaires": 0,
                        "stats_mouvements": {},
                        "total_depots": 0,
                        "total_retraits": 0,
                    },
                )
                self.assertIn("position: running(company-header)", html)
                self.assertIn("position: running(company-footer)", html)
                self.assertIn('counter(pages)', html)

    def test_report_pdf_renders_with_running_header_and_footer(self):
        response = render_pdf(
            "reports/grand_livre.html",
            {
                "site": Site(
                    nom="Shop Central",
                    type_site="shop",
                    adresse="5 rue Principale",
                    ville="Goma",
                ),
                "mouvements": [],
                "debut": None,
                "fin": None,
                "date_generation": timezone.now(),
            },
            "grand_livre.pdf",
        )

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))


class FilteredReportTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(nom="Shop Test", type_site="shop", actif=True)
        self.user = get_user_model().objects.create_user(
            username="caissier",
            password="test-password",
            telephone="0999000002",
            profil="shop",
            site_actif=self.site,
        )
        self.client.force_login(self.user)
        self.matching_transaction = TransactionMobileMoney.objects.create(
            site=self.site,
            agent=self.user,
            type_transaction="depot",
            operateur="mpesa",
            client_nom="Client retenu",
            client_telephone="0999111111",
            montant=Decimal("100.00"),
            frais=Decimal("5.00"),
            devise="USD",
        )
        self.other_transaction = TransactionMobileMoney.objects.create(
            site=self.site,
            agent=self.user,
            type_transaction="retrait",
            operateur="airtel_money",
            client_nom="Autre client",
            client_telephone="0999222222",
            montant=Decimal("50000.00"),
            frais=Decimal("250.00"),
            devise="CDF",
        )

    @patch("reports.views.render_pdf", return_value=HttpResponse("PDF"))
    def test_cash_ledger_report_applies_all_history_filters(self, render_report):
        response = self.client.get(
            reverse("reports:livre_caisse_pdf"),
            {
                "type": "depot",
                "operateur": "mpesa",
                "devise": "USD",
                "debut": timezone.localdate().isoformat(),
                "fin": timezone.localdate().isoformat(),
                "q": "retenu",
            },
        )

        self.assertEqual(response.status_code, 200)
        context = render_report.call_args.args[1]
        self.assertEqual(
            list(context["transactions"].values_list("id", flat=True)),
            [self.matching_transaction.id],
        )
        self.assertEqual(context["totaux_par_devise"]["USD"]["depot"], Decimal("100.00"))
        self.assertEqual(context["totaux_par_devise"]["USD"]["benefice"], Decimal("5.00"))
        self.assertNotIn("CDF", context["totaux_par_devise"])
        self.assertEqual(context["type_transaction"], "depot")
        self.assertEqual(context["operateur"], "mpesa")
        self.assertEqual(context["devise"], "USD")
        self.assertEqual(context["recherche"], "retenu")
        self.assertNotIn(
            self.other_transaction.id,
            list(context["transactions"].values_list("id", flat=True)),
        )

    @patch("reports.views.render_pdf", return_value=HttpResponse("PDF"))
    def test_stock_ledger_report_applies_history_filters(self, render_report):
        categorie = Categorie.objects.create(nom="Outils", site=self.site)
        produit = Produit.objects.create(
            site=self.site,
            categorie=categorie,
            nom="Marteau retenu",
            reference="MAR-01",
            prix_achat=Decimal("5.00"),
            prix_vente=Decimal("10.00"),
            quantite_stock=10,
        )
        matching_movement = MouvementStock.objects.create(
            produit=produit,
            type_mouvement="sortie",
            quantite=-1,
            prix_unitaire=Decimal("10.00"),
            utilisateur=self.user,
        )
        other_movement = MouvementStock.objects.create(
            produit=produit,
            type_mouvement="entree",
            quantite=3,
            prix_unitaire=Decimal("5.00"),
            utilisateur=self.user,
        )

        response = self.client.get(
            reverse("reports:grand_livre_pdf"),
            {
                "type": "sortie",
                "debut": timezone.localdate().isoformat(),
                "fin": timezone.localdate().isoformat(),
                "q": "retenu",
            },
        )

        self.assertEqual(response.status_code, 200)
        context = render_report.call_args.args[1]
        self.assertEqual(
            list(context["mouvements"].values_list("id", flat=True)),
            [matching_movement.id],
        )
        self.assertNotIn(other_movement.id, list(
            context["mouvements"].values_list("id", flat=True)
        ))
        self.assertEqual(context["type_mouvement"], "sortie")
        self.assertEqual(context["recherche"], "retenu")

    def test_stock_report_page_filters_products_and_shows_print_actions(self):
        categorie = Categorie.objects.create(nom="Outils", site=self.site)
        matching = Produit.objects.create(
            site=self.site,
            categorie=categorie,
            nom="Marteau",
            reference="MAR-01",
            prix_achat=Decimal("5.00"),
            prix_vente=Decimal("10.00"),
            quantite_stock=2,
            seuil_alerte=5,
        )
        Produit.objects.create(
            site=self.site,
            categorie=categorie,
            nom="Pelle",
            prix_achat=Decimal("8.00"),
            prix_vente=Decimal("12.00"),
            quantite_stock=20,
            seuil_alerte=5,
        )

        response = self.client.get(
            reverse("reports:rapport_stock"),
            {"rapport": "stock", "alerte": "1", "categorie": categorie.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marteau")
        self.assertNotContains(response, "Pelle")
        self.assertContains(response, "Imprimer")
        self.assertEqual(response.context["nombre_resultats"], 1)
        self.assertEqual(list(response.context["resultats"]), [matching])

    @patch("reports.views.render_pdf", return_value=HttpResponse("PDF"))
    def test_stock_report_pdf_uses_selected_movement_filters_and_inline_print(self, render_report):
        categorie = Categorie.objects.create(nom="Outils", site=self.site)
        produit = Produit.objects.create(
            site=self.site,
            categorie=categorie,
            nom="Marteau",
            reference="MAR-01",
            prix_achat=Decimal("5.00"),
            prix_vente=Decimal("10.00"),
            quantite_stock=10,
        )
        movement = MouvementStock.objects.create(
            produit=produit,
            type_mouvement="sortie",
            quantite=-2,
            prix_unitaire=Decimal("10.00"),
            utilisateur=self.user,
        )

        response = self.client.get(
            reverse("reports:rapport_stock_pdf"),
            {"rapport": "mouvements", "type_mouvement": "sortie", "q": "MAR-01"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(render_report.call_args.args[1]["resultats"]),
            [movement],
        )
        self.assertFalse(render_report.call_args.kwargs["as_attachment"])

        self.client.get(
            reverse("reports:rapport_stock_pdf"),
            {"rapport": "stock", "download": "1"},
        )
        self.assertTrue(render_report.call_args.kwargs["as_attachment"])
