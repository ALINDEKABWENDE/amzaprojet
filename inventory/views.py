from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Count, Sum, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.decorators import site_actif_requis
from .forms import ProduitForm, CategorieForm
from .models import Produit, Categorie, MouvementStock, Vente, LigneVente


class StockInsuffisant(Exception):
    pass


@site_actif_requis
def dashboard(request):
    site = request.user.site_actif
    if site is None:
        return redirect("accounts:choix_profil")

    produits = Produit.objects.filter(site=site)

    valeur_stock = produits.aggregate(
        total=Sum(F("quantite_stock") * F("prix_achat"))
    )["total"] or 0
    nb_alertes = produits.filter(quantite_stock__lte=F("seuil_alerte")).count()
    stock_par_categorie = [
        {"label": ligne["categorie__nom"], "total": ligne["total"] or 0}
        for ligne in
        produits.values("categorie__nom")
        .annotate(total=Sum("quantite_stock"))
        .order_by("categorie__nom")
    ]

    aujourdhui = timezone.localdate()
    debut_defaut = aujourdhui - timedelta(days=6)
    debut = parse_date(request.GET.get("debut", "")) or debut_defaut
    fin = parse_date(request.GET.get("fin", "")) or aujourdhui
    if debut > fin:
        debut, fin = fin, debut

    mouvements_periode = MouvementStock.objects.filter(
        produit__site=site,
        date_mouvement__date__gte=debut,
        date_mouvement__date__lte=fin,
    )
    stats_mouvements = mouvements_periode.aggregate(
        ventes=Sum("quantite", filter=Q(type_mouvement="sortie")),
        entrees=Sum("quantite", filter=Q(type_mouvement="entree")),
        ajustements=Count("id", filter=Q(type_mouvement="ajustement")),
        chiffre_affaires=Sum(
            F("quantite") * F("prix_unitaire"),
            filter=Q(type_mouvement="sortie"),
        ),
    )
    mouvements_journaliers = mouvements_periode.annotate(
        jour=TruncDate("date_mouvement")
    ).values("jour", "type_mouvement").annotate(total=Count("id")).order_by("jour")
    dates_mouvements = sorted({ligne["jour"] for ligne in mouvements_journaliers})
    compteurs_par_jour = defaultdict(dict)
    for ligne in mouvements_journaliers:
        compteurs_par_jour[ligne["jour"]][ligne["type_mouvement"]] = ligne["total"]

    context = {
        "site": site,
        "nombre_produits": produits.count(),
        "valeur_stock": valeur_stock,
        "nb_alertes": nb_alertes,
        "stock_par_categorie": stock_par_categorie,
        "debut_stats": debut.isoformat(),
        "fin_stats": fin.isoformat(),
        "stats_mouvements": stats_mouvements,
        "labels_mouvements": [jour.strftime("%d/%m") for jour in dates_mouvements],
        "ventes_par_jour": [compteurs_par_jour[jour].get("sortie", 0) for jour in dates_mouvements],
        "entrees_par_jour": [compteurs_par_jour[jour].get("entree", 0) for jour in dates_mouvements],
        "ajustements_par_jour": [compteurs_par_jour[jour].get("ajustement", 0) for jour in dates_mouvements],
    }
    return render(request, "inventory/dashboard.html", context)


@site_actif_requis
def produits(request):
    site = request.user.site_actif
    queryset = Produit.objects.filter(site=site).select_related("categorie")

    categorie_id = request.GET.get("categorie", "").strip()
    if categorie_id.isdigit():
        queryset = queryset.filter(categorie_id=categorie_id)
    else:
        categorie_id = ""

    recherche = request.GET.get("q", "").strip()
    if recherche:
        queryset = queryset.filter(
            Q(nom__icontains=recherche) | Q(reference__icontains=recherche)
        )

    stock_alerte = request.GET.get("alerte") == "1"
    if stock_alerte:
        queryset = queryset.filter(quantite_stock__lte=F("seuil_alerte"))

    queryset = queryset.order_by("nom")
    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    querystring = request.GET.copy()
    querystring.pop("page", None)

    produits_site = Produit.objects.filter(site=site)
    context = {
        "site": site,
        "produits": page_obj,
        "page_obj": page_obj,
        "querystring": querystring.urlencode(),
        "categories": Categorie.objects.filter(site=site).order_by("nom"),
        "categorie_active": categorie_id,
        "recherche": recherche,
        "alerte_active": stock_alerte,
        "nombre_produits": produits_site.count(),
        "nombre_alertes": produits_site.filter(
            quantite_stock__lte=F("seuil_alerte")
        ).count(),
    }
    return render(request, "inventory/produits.html", context)


@site_actif_requis
def ajuster_stock(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id, site=request.user.site_actif)

    if request.method == "POST":
        quantite = int(request.POST.get("quantite", 0))
        type_mouvement = request.POST.get("type_mouvement", "ajustement")

        if type_mouvement == "sortie" and quantite > produit.quantite_stock:
            messages.error(request, f"Stock insuffisant pour « {produit.nom} » (disponible : {produit.quantite_stock}).")
            return redirect("inventory:dashboard")

        MouvementStock.objects.create(
            produit=produit,
            type_mouvement=type_mouvement,
            quantite=quantite,
            prix_unitaire=produit.prix_vente,
            utilisateur=request.user,
        )

        if type_mouvement == "sortie":
            produit.quantite_stock = max(0, produit.quantite_stock - quantite)
        else:
            produit.quantite_stock += quantite
        produit.save(update_fields=["quantite_stock"])

        mouvement = MouvementStock.objects.filter(produit=produit).latest("date_mouvement")
        if type_mouvement == "sortie":
            # Redirige directement vers la facture PDF téléchargeable de la vente
            return redirect("reports:facture_pdf", mouvement_id=mouvement.id)

        messages.success(request, f"Mouvement enregistré pour « {produit.nom} ».")

    return redirect("inventory:dashboard")


@site_actif_requis
def nouvelle_vente(request):
    site = request.user.site_actif
    if site is None:
        return redirect("accounts:choix_profil")

    produits = list(Produit.objects.filter(site=site).select_related("categorie").order_by("nom"))
    quantites = {}
    erreur = ""

    if request.method == "POST":
        lignes_a_vendre = []
        for produit in produits:
            valeur = request.POST.get(f"quantite_{produit.id}", "0").strip()
            quantites[produit.id] = valeur
            try:
                quantite = int(valeur or "0")
            except ValueError:
                erreur = f"La quantité pour « {produit.nom} » doit être un nombre entier."
                break

            if quantite < 0:
                erreur = f"La quantité pour « {produit.nom} » ne peut pas être négative."
                break
            if quantite:
                lignes_a_vendre.append((produit, quantite))

        if not erreur and not lignes_a_vendre:
            erreur = "Saisissez une quantité pour au moins un produit."

        if not erreur:
            try:
                with transaction.atomic():
                    vente = Vente.objects.create(site=site, utilisateur=request.user)
                    for produit, quantite in lignes_a_vendre:
                        if quantite > produit.quantite_stock:
                            raise StockInsuffisant(
                                f"Stock insuffisant pour « {produit.nom} » "
                                f"(disponible : {produit.quantite_stock})."
                            )
                        stock_modifie = Produit.objects.filter(
                            id=produit.id,
                            site=site,
                            quantite_stock__gte=quantite,
                        ).update(quantite_stock=F("quantite_stock") - quantite)
                        if not stock_modifie:
                            produit.refresh_from_db()
                            raise StockInsuffisant(
                                f"Stock insuffisant pour « {produit.nom} » "
                                f"(disponible : {produit.quantite_stock})."
                            )

                        LigneVente.objects.create(
                            vente=vente,
                            produit=produit,
                            quantite=quantite,
                            prix_unitaire=produit.prix_vente,
                        )
                        MouvementStock.objects.create(
                            produit=produit,
                            vente=vente,
                            type_mouvement="sortie",
                            quantite=quantite,
                            prix_unitaire=produit.prix_vente,
                            utilisateur=request.user,
                            note=f"Vente n°{vente.id}",
                        )
            except StockInsuffisant as exc:
                erreur = str(exc)
            else:
                return redirect("reports:vente_ticket_pdf", vente_id=vente.id)

    if erreur:
        messages.error(request, erreur)

    lignes_produits = [
        {"produit": produit, "quantite": quantites.get(produit.id, "0")}
        for produit in produits
    ]
    return render(request, "inventory/vente_form.html", {
        "site": site,
        "lignes_produits": lignes_produits,
    })


@site_actif_requis
def produit_ajouter(request):
    site = request.user.site_actif
    if site is None:
        return redirect("accounts:choix_profil")

    if not Categorie.objects.filter(site=site).exists():
        messages.warning(request, "Créez d'abord une catégorie avant d'ajouter un produit.")
        return redirect("inventory:categorie_ajouter")

    if request.method == "POST":
        form = ProduitForm(request.POST, site=site)
        if form.is_valid():
            produit = form.save(commit=False)
            produit.site = site
            produit.save()
            if produit.quantite_stock:
                MouvementStock.objects.create(
                    produit=produit, type_mouvement="entree",
                    quantite=produit.quantite_stock, prix_unitaire=produit.prix_achat,
                    utilisateur=request.user, note="Stock initial à la création du produit",
                )
            messages.success(request, f"Produit « {produit.nom} » ajouté.")
            return redirect("inventory:produits")
    else:
        form = ProduitForm(site=site)

    return render(request, "inventory/produit_form.html", {"form": form, "mode": "ajouter"})


@site_actif_requis
def produit_modifier(request, produit_id):
    site = request.user.site_actif
    produit = get_object_or_404(Produit, id=produit_id, site=site)

    if request.method == "POST":
        form = ProduitForm(request.POST, instance=produit, site=site)
        if form.is_valid():
            form.save()
            messages.success(request, f"Produit « {produit.nom} » mis à jour.")
            return redirect("inventory:produits")
    else:
        form = ProduitForm(instance=produit, site=site)

    return render(request, "inventory/produit_form.html", {"form": form, "mode": "modifier", "produit": produit})


@site_actif_requis
def produit_supprimer(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id, site=request.user.site_actif)
    if request.method == "POST":
        nom = produit.nom
        produit.delete()
        messages.success(request, f"Produit « {nom} » supprimé.")
        return redirect("inventory:produits")
    return render(request, "inventory/produit_confirmer_suppression.html", {"produit": produit})


@site_actif_requis
def categorie_ajouter(request):
    site = request.user.site_actif
    if site is None:
        return redirect("accounts:choix_profil")

    if request.method == "POST":
        form = CategorieForm(request.POST)
        if form.is_valid():
            categorie = form.save(commit=False)
            categorie.site = site
            categorie.save()
            messages.success(request, f"Catégorie « {categorie.nom} » créée.")
            return redirect("inventory:dashboard")
    else:
        form = CategorieForm()

    categories = Categorie.objects.filter(site=site).annotate(product_count=Count("produits")).order_by("nom")
    context = {
        "form": form,
        "categories": categories,
        "nombre_produits_classes": Produit.objects.filter(site=site).count(),
    }
    return render(request, "inventory/categorie_form.html", context)


@site_actif_requis
def historique(request):
    """Historique complet, paginé et filtrable, des mouvements de stock (ventes, entrées, ajustements)."""
    site = request.user.site_actif
    if site is None:
        return redirect("accounts:choix_profil")

    mouvements = MouvementStock.objects.filter(produit__site=site).select_related(
        "produit", "produit__categorie", "utilisateur"
    )

    type_mouvement = request.GET.get("type", "")
    if type_mouvement in ("entree", "sortie", "ajustement"):
        mouvements = mouvements.filter(type_mouvement=type_mouvement)

    debut = request.GET.get("debut", "")
    if debut and parse_date(debut):
        mouvements = mouvements.filter(date_mouvement__date__gte=parse_date(debut))

    fin = request.GET.get("fin", "")
    if fin and parse_date(fin):
        mouvements = mouvements.filter(date_mouvement__date__lte=parse_date(fin))

    recherche = request.GET.get("q", "").strip()
    if recherche:
        mouvements = mouvements.filter(
            Q(produit__nom__icontains=recherche) | Q(produit__reference__icontains=recherche)
        )

    mouvements = mouvements.order_by("-date_mouvement")

    ventes = mouvements.filter(type_mouvement="sortie")
    chiffre_affaires = ventes.aggregate(total=Sum(F("quantite") * F("prix_unitaire")))["total"] or 0

    paginator = Paginator(mouvements, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    querystring = request.GET.copy()
    querystring.pop("page", None)

    context = {
        "site": site,
        "mouvements": page_obj,
        "page_obj": page_obj,
        "filtres": {"type": type_mouvement, "debut": debut, "fin": fin, "q": recherche},
        "chiffre_affaires": chiffre_affaires,
        "nb_ventes": ventes.count(),
        "querystring": querystring.urlencode(),
    }
    return render(request, "inventory/historique.html", context)
