from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from .models import Site
from inventory.models import Categorie, MouvementStock, Produit
from pos.models import TransactionMobileMoney


class SiteApprovalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nouvel-agent",
            password="test-password",
            telephone="0999000081",
            profil="shop",
        )
        self.client.force_login(self.user)

    def test_administration_page_renders_sites_without_responsables(self):
        admin = get_user_model().objects.create_user(
            username="admin-sans-vendeurs",
            password="test-password",
            telephone="0999000090",
            profil="shop",
            is_staff=True,
        )
        Site.objects.create(nom="Site en attente sans responsable", type_site="shop")
        Site.objects.create(
            nom="Site actif sans responsable",
            type_site="quincaillerie",
            actif=True,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("core:administration"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Site en attente sans responsable")
        self.assertContains(response, "Site actif sans responsable")
        self.assertGreaterEqual(response.content.count("—".encode()), 2)

    def test_new_site_is_created_pending_and_cannot_access_dashboard(self):
        response = self.client.post(
            reverse("accounts:choix_profil"),
            {"profil": "shop", "nom_site": "Nouveau Shop", "ville": "Kinshasa"},
            follow=True,
        )

        site = Site.objects.get(nom="Nouveau Shop")
        self.assertFalse(site.actif)
        self.assertEqual(response.request["PATH_INFO"], reverse("core:site_en_attente"))
        self.assertContains(response, "Votre site attend une autorisation")

        response = self.client.get(reverse("pos:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:site_en_attente"))
        self.assertEqual(
            self.client.get(reverse("core:site_en_attente")).status_code,
            200,
        )

    def test_only_staff_can_approve_a_site(self):
        site = Site.objects.create(nom="À valider", type_site="shop")
        response = self.client.post(
            reverse("core:site_approbation", args=[site.pk]),
            {"actif": "true"},
        )

        site.refresh_from_db()
        self.assertFalse(site.actif)
        self.assertEqual(response.status_code, 302)

        admin = get_user_model().objects.create_user(
            username="gestionnaire",
            password="test-password",
            telephone="0999000082",
            profil="shop",
            is_staff=True,
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("core:site_approbation", args=[site.pk]),
            {"actif": "true"},
        )

        site.refresh_from_db()
        self.assertTrue(site.actif)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:administration"))

    def test_approved_site_can_open_its_dashboard(self):
        site = Site.objects.create(nom="Shop approuvé", type_site="shop")
        site.vendeurs.add(self.user)
        self.user.site_actif = site
        self.user.save(update_fields=["site_actif"])
        admin = get_user_model().objects.create_user(
            username="approbateur",
            password="test-password",
            telephone="0999000086",
            profil="shop",
            is_staff=True,
        )
        self.client.force_login(admin)
        self.client.post(
            reverse("core:site_approbation", args=[site.pk]),
            {"actif": "true"},
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("pos:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_manage_both_shop_and_hardware_sites(self):
        admin = get_user_model().objects.create_user(
            username="admin-deux-activites",
            password=None,
            telephone="0999000091",
            profil="shop",
            is_staff=True,
        )
        site_stock = Site.objects.create(
            nom="Quincaillerie administrée", type_site="quincaillerie", actif=True
        )
        site_shop = Site.objects.create(
            nom="Shop administré", type_site="shop", actif=True
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("core:changer_site", args=[site_stock.pk]))
        self.assertRedirects(response, reverse("inventory:dashboard"))
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quincaillerie administrée")

        response = self.client.get(reverse("core:changer_site", args=[site_shop.pk]))
        self.assertRedirects(response, reverse("pos:dashboard"))
        response = self.client.get(reverse("pos:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shop administré")

    def test_non_staff_cannot_switch_to_an_unassigned_site(self):
        site = Site.objects.create(
            nom="Site non attribué", type_site="quincaillerie", actif=True
        )

        response = self.client.get(reverse("core:changer_site", args=[site.pk]))

        self.assertEqual(response.status_code, 404)


class GlobalAdministrationReportTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="rapport-admin",
            password="test-password",
            telephone="0999000083",
            profil="shop",
            is_staff=True,
        )
        self.user = get_user_model().objects.create_user(
            username="agent-rapport",
            password="test-password",
            telephone="0999000084",
            profil="shop",
        )
        self.site_shop = Site.objects.create(nom="Shop Central", type_site="shop", actif=True)
        self.site_stock = Site.objects.create(
            nom="Quincaillerie Nord", type_site="quincaillerie", actif=True
        )
        self.user.sites.add(self.site_shop, self.site_stock)
        self.user.site_actif = self.site_shop
        self.user.save(update_fields=["site_actif"])
        TransactionMobileMoney.objects.create(
            site=self.site_shop,
            agent=self.user,
            type_transaction="depot",
            operateur="mpesa",
            client_nom="Client global",
            client_telephone="0999000085",
            montant=Decimal("100.00"),
            frais=Decimal("5.00"),
        )
        categorie = Categorie.objects.create(nom="Outils", site=self.site_stock)
        produit = Produit.objects.create(
            site=self.site_stock,
            categorie=categorie,
            nom="Marteau",
            prix_achat=Decimal("10.00"),
            prix_vente=Decimal("15.00"),
        )
        MouvementStock.objects.create(
            produit=produit,
            type_mouvement="entree",
            quantite=4,
            prix_unitaire=Decimal("10.00"),
            utilisateur=self.user,
        )

    def test_staff_can_view_and_filter_reports_across_sites(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("reports:rapports_administration"),
            {"type": "caisse"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shop Central")
        self.assertContains(response, "100,00")

        response = self.client.get(
            reverse("reports:rapports_administration"),
            {"type": "stock", "site": self.site_stock.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marteau")
        self.assertContains(response, "Quincaillerie Nord")
        self.assertNotContains(response, "Client global")
        self.assertContains(response, "admin-report-document-header")
        self.assertContains(response, "admin-report-summary")

    def test_global_report_paginates_and_preserves_filters(self):
        for number in range(11):
            TransactionMobileMoney.objects.create(
                site=self.site_shop,
                agent=self.user,
                type_transaction="depot",
                operateur="mpesa",
                client_nom=f"Pagination client {number}",
                client_telephone=f"09991112{number:02d}",
                montant=Decimal("10.00"),
            )

        self.client.force_login(self.admin)
        params = {
            "type": "caisse",
            "site": self.site_shop.pk,
            "par_page": "10",
        }
        first_page = self.client.get(reverse("reports:rapports_administration"), params)
        second_page = self.client.get(
            reverse("reports:rapports_administration"),
            {**params, "page": 2},
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["page_obj"].paginator.count, 12)
        self.assertEqual(len(first_page.context["lignes"]), 10)
        self.assertContains(first_page, "Affichage de")
        self.assertContains(first_page, "par_page=10")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(len(second_page.context["lignes"]), 2)
        self.assertContains(second_page, "site=" + str(self.site_shop.pk))

    def test_non_staff_cannot_view_global_reports(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:rapports_administration"))

        self.assertEqual(response.status_code, 302)

    @patch("reports.views.render_pdf", return_value=HttpResponse("PDF"))
    def test_staff_can_export_a_filtered_global_report(self, render_report):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("reports:rapports_administration_pdf"),
            {"type": "stock", "site": self.site_stock.pk},
        )

        self.assertEqual(response.status_code, 200)
        context = render_report.call_args.args[1]
        self.assertEqual(context["site_selectionne"], self.site_stock)
        self.assertEqual(context["lignes"].count(), 1)
        self.assertTrue(context["mode_pdf"])

    def test_staff_pdf_report_renders_with_the_shared_administration_design(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("reports:rapports_administration_pdf"),
            {"type": "caisse", "site": self.site_shop.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
