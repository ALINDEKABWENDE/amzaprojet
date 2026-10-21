from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Site
from .models import Categorie, LigneVente, MouvementStock, Produit, Vente


class NouvelleVenteTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(nom="Quincaillerie Test", type_site="quincaillerie", actif=True)
        self.user = get_user_model().objects.create_user(
            username="vendeur",
            password="secret",
            telephone="0999000001",
            profil="quincaillerie",
            site_actif=self.site,
        )
        self.user.sites.add(self.site)
        categorie = Categorie.objects.create(nom="Matériaux", site=self.site)
        self.clou = Produit.objects.create(
            site=self.site,
            categorie=categorie,
            nom="Clou",
            prix_achat=Decimal("1.00"),
            prix_vente=Decimal("2.50"),
            quantite_stock=10,
        )
        self.ciment = Produit.objects.create(
            site=self.site,
            categorie=categorie,
            nom="Sac de ciment",
            prix_achat=Decimal("15.00"),
            prix_vente=Decimal("20.00"),
            quantite_stock=5,
        )
        self.client.force_login(self.user)

    def test_creates_multi_product_sale_and_one_invoice(self):
        response = self.client.post(
            reverse("inventory:nouvelle_vente"),
            {
                f"quantite_{self.clou.id}": "2",
                f"quantite_{self.ciment.id}": "3",
            },
        )

        vente = Vente.objects.get()
        self.assertRedirects(
            response,
            reverse("reports:vente_ticket_pdf", args=[vente.id]),
            fetch_redirect_response=False,
        )
        self.clou.refresh_from_db()
        self.ciment.refresh_from_db()
        self.assertEqual(self.clou.quantite_stock, 8)
        self.assertEqual(self.ciment.quantite_stock, 2)
        self.assertEqual(vente.lignes.count(), 2)
        self.assertEqual(vente.total, Decimal("65.00"))
        self.assertEqual(MouvementStock.objects.filter(vente=vente, type_mouvement="sortie").count(), 2)

        with patch("reports.views.render_pdf", return_value=HttpResponse("PDF")) as render_pdf:
            facture = self.client.get(reverse("reports:vente_pdf", args=[vente.id]))
        self.assertEqual(facture.content, b"PDF")
        context = render_pdf.call_args.args[1]
        self.assertEqual(len(context["lignes"]), 2)
        self.assertEqual(context["total"], Decimal("65.00"))

    def test_sale_receipt_is_available_as_a_thermal_pdf(self):
        with patch("reports.views.render_pdf", return_value=HttpResponse("PDF")) as render_pdf:
            response = self.client.get(
                reverse("reports:vente_ticket_pdf", args=[self._create_sale()])
            )

        self.assertEqual(response.content, b"PDF")
        template_name, context, filename = render_pdf.call_args.args
        self.assertEqual(template_name, "reports/ticket_vente_thermique.html")
        self.assertEqual(context["total"], Decimal("65.00"))
        self.assertEqual(len(context["lignes"]), 2)
        self.assertEqual(filename, f"recu_vente_{context['vente'].id}.pdf")

    def _create_sale(self):
        response = self.client.post(
            reverse("inventory:nouvelle_vente"),
            {
                f"quantite_{self.clou.id}": "2",
                f"quantite_{self.ciment.id}": "3",
            },
        )
        self.assertEqual(response.status_code, 302)
        return Vente.objects.latest("id").id

    def test_rejects_insufficient_stock_without_partial_sale(self):
        response = self.client.post(
            reverse("inventory:nouvelle_vente"),
            {
                f"quantite_{self.clou.id}": "2",
                f"quantite_{self.ciment.id}": "6",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stock insuffisant")
        self.assertFalse(Vente.objects.exists())
        self.assertFalse(LigneVente.objects.exists())
        self.assertFalse(MouvementStock.objects.exists())
        self.clou.refresh_from_db()
        self.ciment.refresh_from_db()
        self.assertEqual(self.clou.quantite_stock, 10)
        self.assertEqual(self.ciment.quantite_stock, 5)

    def test_rejects_empty_sale(self):
        response = self.client.post(reverse("inventory:nouvelle_vente"), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "au moins un produit")
        self.assertFalse(Vente.objects.exists())

    def test_dashboard_exposes_multi_product_checkout(self):
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestion stock")
        self.assertContains(response, 'id="hardwareMenu"')
        self.assertContains(response, "dropdown-menu hardware-nav-menu")
        self.assertContains(response, "Tableau de bord")
        self.assertContains(response, "Produits")
        self.assertContains(response, "Historique")
        self.assertContains(response, "Rapports")
        self.assertContains(response, reverse("inventory:nouvelle_vente"))
        self.assertContains(response, reverse("inventory:produits"))
        self.assertContains(response, "Consulter les produits")
        self.assertNotContains(response, "Sac de ciment")

    def test_product_catalog_lists_and_filters_only_current_site_products(self):
        response = self.client.get(reverse("inventory:produits"), {"q": "clou"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clou")
        self.assertNotContains(response, "Sac de ciment")
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_add_product_page_renders_the_product_entry_form(self):
        response = self.client.get(reverse("inventory:produit_ajouter"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informations du produit")
        self.assertContains(response, "Prix et disponibilité")
        self.assertContains(response, "Ajouter le produit")

    def test_category_page_shows_styled_list_and_product_counts(self):
        response = self.client.get(reverse("inventory:categorie_ajouter"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Créer une catégorie")
        self.assertContains(response, "Catégories existantes")
        self.assertContains(response, "Matériaux")
        self.assertContains(response, "2 produit")
        self.assertEqual(response.context["nombre_produits_classes"], 2)
        self.assertEqual(response.context["categories"][0].product_count, 2)

    def test_category_page_creates_category_and_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("inventory:categorie_ajouter"),
            {"nom": "Électricité"},
        )

        self.assertRedirects(response, reverse("inventory:dashboard"))
        self.assertTrue(
            Categorie.objects.filter(site=self.site, nom="Électricité").exists()
        )

    def test_product_catalog_paginates_and_preserves_filters(self):
        for index in range(13):
            Produit.objects.create(
                site=self.site,
                categorie=self.clou.categorie,
                nom=f"Vis {index:02}",
                prix_achat=Decimal("1.00"),
                prix_vente=Decimal("1.50"),
                quantite_stock=3,
            )

        response = self.client.get(
            reverse("inventory:produits"),
            {"categorie": self.clou.categorie_id, "alerte": "1", "page": "2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertContains(response, "categorie=")
        self.assertContains(response, "alerte=1")
        self.assertEqual(response.context["page_obj"].paginator.count, 14)
        self.assertEqual(len(response.context["page_obj"].object_list), 2)

    def test_checkout_shows_cart_summary_and_quantity_controls(self):
        response = self.client.get(reverse("inventory:nouvelle_vente"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="saleTotal"')
        self.assertContains(response, 'data-quantity-step="1"')
        self.assertContains(response, "Enregistrer et imprimer le reçu")
        self.assertContains(response, 'id="saleProductSearch"')
        self.assertContains(response, 'aria-controls="saleProductList"')
        self.assertContains(response, 'id="saleSearchEmpty"')
        self.assertContains(response, "data-search-text=")

    def test_dashboard_shows_period_filtered_chart_statistics(self):
        MouvementStock.objects.create(
            produit=self.clou,
            type_mouvement="sortie",
            quantite=2,
            prix_unitaire=Decimal("2.50"),
            utilisateur=self.user,
        )
        today = timezone.localdate().isoformat()

        response = self.client.get(
            reverse("inventory:dashboard"),
            {"debut": today, "fin": today},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats_mouvements"]["ventes"], 2)
        self.assertEqual(response.context["stats_mouvements"]["chiffre_affaires"], Decimal("5.00"))
        self.assertEqual(response.context["labels_mouvements"], [timezone.localdate().strftime("%d/%m")])
        self.assertContains(response, 'id="stockCategoryChart"')
        self.assertContains(response, 'id="stockActivityChart"')
