from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.db.models.functions import Abs
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.decorators import site_actif_requis
from core.models import Site
from inventory.models import Categorie, MouvementStock, Produit, Vente
from pos.models import TransactionMobileMoney
from .pdf_utils import render_pdf


@site_actif_requis
def facture_pdf(request, mouvement_id):
    """Facture imprimable pour une sortie de stock (vente)."""
    mouvement = get_object_or_404(MouvementStock, id=mouvement_id, produit__site=request.user.site_actif)
    total = mouvement.quantite * mouvement.prix_unitaire
    date_emission = timezone.now()
    context = {
        "mouvement": mouvement,
        "site": mouvement.produit.site,
        "total": total,
        "date_emission": date_emission,
        "entete_document": "FACTURE",
        "reference_document": mouvement.id,
        "date_document": date_emission,
    }
    filename = f"facture_{mouvement.id}.pdf"
    return render_pdf("reports/facture.html", context, filename)


@site_actif_requis
def vente_pdf(request, vente_id):
    """Facture unique regroupant tous les articles d'une vente."""
    vente = get_object_or_404(
        Vente.objects.filter(site=request.user.site_actif).prefetch_related("lignes__produit"),
        id=vente_id,
    )
    lignes = vente.lignes.all()
    context = {
        "vente": vente,
        "lignes": lignes,
        "site": vente.site,
        "total": vente.total,
        "entete_document": "FACTURE",
        "reference_document": vente.id,
        "date_document": vente.date_vente,
    }
    filename = f"facture_vente_{vente.id}.pdf"
    return render_pdf("reports/facture_vente.html", context, filename)


@site_actif_requis
def vente_ticket_pdf(request, vente_id):
    """Ticket thermique récapitulatif d'une vente de quincaillerie."""
    vente = get_object_or_404(
        Vente.objects.filter(site=request.user.site_actif).prefetch_related("lignes__produit"),
        id=vente_id,
    )
    context = {
        "vente": vente,
        "lignes": vente.lignes.all(),
        "site": vente.site,
        "total": vente.total,
        "entete_document": "REÇU DE VENTE",
        "reference_document": vente.id,
        "date_document": vente.date_vente,
    }
    filename = f"recu_vente_{vente.id}.pdf"
    return render_pdf("reports/ticket_vente_thermique.html", context, filename)


@site_actif_requis
def ticket_pdf(request, transaction_id):
    """Ticket de caisse format imprimante thermique (80mm) pour mobile money."""
    transaction = get_object_or_404(
        TransactionMobileMoney, id=transaction_id, site=request.user.site_actif
    )
    context = {
        "t": transaction,
        "site": transaction.site,
        "entete_document": "TICKET DE CAISSE",
        "reference_document": transaction.id,
        "date_document": transaction.date_transaction,
    }
    filename = f"ticket_{transaction.id}.pdf"
    return render_pdf("reports/ticket_thermique.html", context, filename)


@site_actif_requis
def grand_livre_pdf(request):
    """Grand livre de stock : tous les mouvements sur une période donnée."""
    site = request.user.site_actif
    debut = parse_date(request.GET.get("debut", "")) if request.GET.get("debut") else None
    fin = parse_date(request.GET.get("fin", "")) if request.GET.get("fin") else None
    type_mouvement = request.GET.get("type", "")
    recherche = request.GET.get("q", "").strip()

    mouvements = MouvementStock.objects.filter(produit__site=site).select_related(
        "produit", "produit__categorie", "utilisateur"
    )
    if type_mouvement in ("entree", "sortie", "ajustement"):
        mouvements = mouvements.filter(type_mouvement=type_mouvement)
    if debut:
        mouvements = mouvements.filter(date_mouvement__date__gte=debut)
    if fin:
        mouvements = mouvements.filter(date_mouvement__date__lte=fin)
    if recherche:
        mouvements = mouvements.filter(
            Q(produit__nom__icontains=recherche) | Q(produit__reference__icontains=recherche)
        )

    context = {
        "site": site,
        "mouvements": mouvements,
        "debut": debut,
        "fin": fin,
        "type_mouvement": type_mouvement,
        "recherche": recherche,
        "date_generation": timezone.now(),
        "entete_document": "GRAND LIVRE DE STOCK",
        "date_document": timezone.now(),
    }
    filename = f"grand_livre_stock_{site.id}.pdf"
    return render_pdf("reports/grand_livre.html", context, filename)


def _rapport_stock_context(request, site):
    type_rapport = request.GET.get("rapport", "stock")
    if type_rapport not in ("stock", "mouvements"):
        raise Http404("Type de rapport inconnu.")

    categories = Categorie.objects.filter(site=site).order_by("nom")
    categorie_id = request.GET.get("categorie", "").strip()
    if categorie_id and (
        not categorie_id.isdigit() or not categories.filter(pk=categorie_id).exists()
    ):
        raise Http404("Catégorie inconnue.")

    recherche = request.GET.get("q", "").strip()
    alerte_seulement = request.GET.get("alerte") == "1"
    type_mouvement = request.GET.get("type_mouvement", "")
    if type_mouvement and type_mouvement not in ("entree", "sortie", "ajustement"):
        raise Http404("Type de mouvement inconnu.")

    debut_brut = request.GET.get("debut", "")
    fin_brut = request.GET.get("fin", "")
    debut = parse_date(debut_brut) if debut_brut else None
    fin = parse_date(fin_brut) if fin_brut else None
    if (debut_brut and debut is None) or (fin_brut and fin is None):
        raise Http404("Date de rapport invalide.")
    if debut and fin and debut > fin:
        raise Http404("La date de début doit précéder la date de fin.")

    if type_rapport == "stock":
        resultats = Produit.objects.filter(site=site).select_related("categorie")
        if categorie_id:
            resultats = resultats.filter(categorie_id=categorie_id)
        if recherche:
            resultats = resultats.filter(
                Q(nom__icontains=recherche) | Q(reference__icontains=recherche)
            )
        if alerte_seulement:
            resultats = resultats.filter(quantite_stock__lte=F("seuil_alerte"))
        resultats = resultats.order_by("categorie__nom", "nom")
        agregats = resultats.aggregate(
            total_quantite=Sum("quantite_stock"),
            total_valeur=Sum(F("quantite_stock") * F("prix_achat")),
        )
        totaux = {
            "quantite": agregats["total_quantite"] or 0,
            "valeur": agregats["total_valeur"] or 0,
        }
        nombre_alertes = resultats.filter(
            quantite_stock__lte=F("seuil_alerte")
        ).count()
    else:
        resultats = MouvementStock.objects.filter(
            produit__site=site
        ).select_related("produit", "produit__categorie", "utilisateur")
        if categorie_id:
            resultats = resultats.filter(produit__categorie_id=categorie_id)
        if type_mouvement:
            resultats = resultats.filter(type_mouvement=type_mouvement)
        if debut:
            resultats = resultats.filter(date_mouvement__date__gte=debut)
        if fin:
            resultats = resultats.filter(date_mouvement__date__lte=fin)
        if recherche:
            resultats = resultats.filter(
                Q(produit__nom__icontains=recherche)
                | Q(produit__reference__icontains=recherche)
            )
        resultats = resultats.order_by("-date_mouvement")
        agregats = resultats.aggregate(
            total_quantite=Sum(Abs("quantite")),
            total_valeur=Sum(Abs(F("quantite") * F("prix_unitaire"))),
        )
        totaux = {
            "quantite": agregats["total_quantite"] or 0,
            "valeur": agregats["total_valeur"] or 0,
        }
        nombre_alertes = 0

    return {
        "site": site,
        "type_rapport": type_rapport,
        "categories": categories,
        "categorie_active": categorie_id,
        "recherche": recherche,
        "alerte_seulement": alerte_seulement,
        "type_mouvement": type_mouvement,
        "debut": debut,
        "fin": fin,
        "resultats": resultats,
        "nombre_resultats": resultats.count(),
        "nombre_alertes": nombre_alertes,
        "totaux": totaux,
        "date_generation": timezone.now(),
        "entete_document": "ÉTAT DU STOCK" if type_rapport == "stock" else "GRAND LIVRE DE STOCK",
    }


@site_actif_requis
def rapport_stock(request):
    context = _rapport_stock_context(request, request.user.site_actif)
    page_size = request.GET.get("par_page", "15")
    if page_size not in ("12", "15", "30"):
        page_size = "15"
    page_obj = Paginator(context["resultats"], int(page_size)).get_page(request.GET.get("page"))
    querystring = request.GET.copy()
    querystring.pop("page", None)
    context.update({
        "page_obj": page_obj,
        "resultats": page_obj,
        "page_size": page_size,
        "querystring": querystring.urlencode(),
    })
    return render(request, "reports/rapport_stock.html", context)


@site_actif_requis
def rapport_stock_pdf(request):
    context = _rapport_stock_context(request, request.user.site_actif)
    filename = f"rapport_{context['type_rapport']}_{context['site'].id}.pdf"
    context["reference_document"] = context["site"].id
    return render_pdf(
        "reports/rapport_stock_pdf.html",
        context,
        filename,
        as_attachment=request.GET.get("download") == "1",
    )


@site_actif_requis
def fiche_produit_pdf(request, produit_id):
    """Fiche de stock détaillée pour un produit (tous ses mouvements)."""
    produit = get_object_or_404(Produit, id=produit_id, site=request.user.site_actif)
    mouvements = produit.mouvements.select_related("utilisateur")
    context = {
        "produit": produit,
        "site": produit.site,
        "mouvements": mouvements,
        "date_generation": timezone.now(),
        "entete_document": "FICHE DE STOCK",
        "reference_document": produit.reference or produit.id,
        "date_document": timezone.now(),
    }
    filename = f"fiche_{produit.reference or produit.id}.pdf"
    return render_pdf("reports/fiche_produit.html", context, filename)


@site_actif_requis
def livre_caisse_pdf(request):
    """Livre de caisse : tous les dépôts/retraits mobile money sur une période."""
    site = request.user.site_actif
    debut = parse_date(request.GET.get("debut", "")) if request.GET.get("debut") else None
    fin = parse_date(request.GET.get("fin", "")) if request.GET.get("fin") else None
    type_transaction = request.GET.get("type", "")
    operateur = request.GET.get("operateur", "")
    devise = request.GET.get("devise", "")
    recherche = request.GET.get("q", "").strip()

    transactions = TransactionMobileMoney.objects.filter(site=site).select_related("agent")
    if type_transaction in ("depot", "retrait"):
        transactions = transactions.filter(type_transaction=type_transaction)
    if operateur:
        transactions = transactions.filter(operateur=operateur)
    if devise in ("USD", "CDF"):
        transactions = transactions.filter(devise=devise)
    if debut:
        transactions = transactions.filter(date_transaction__date__gte=debut)
    if fin:
        transactions = transactions.filter(date_transaction__date__lte=fin)
    if recherche:
        transactions = transactions.filter(
            Q(client_nom__icontains=recherche) | Q(client_telephone__icontains=recherche)
        )
    transactions = transactions.order_by("date_transaction")

    totaux_par_devise = {}
    for ligne in transactions.order_by().values("devise").annotate(
        depots=Sum("montant", filter=Q(type_transaction="depot")),
        retraits=Sum("montant", filter=Q(type_transaction="retrait")),
        benefice=Sum("frais"),
    ):
        totaux_par_devise[ligne["devise"]] = {
            "depot": ligne["depots"] or 0,
            "retrait": ligne["retraits"] or 0,
            "benefice": ligne["benefice"] or 0,
        }

    context = {
        "site": site,
        "transactions": transactions,
        "debut": debut,
        "fin": fin,
        "type_transaction": type_transaction,
        "operateur": operateur,
        "devise": devise,
        "recherche": recherche,
        "totaux_par_devise": totaux_par_devise,
        "date_generation": timezone.now(),
        "entete_document": "LIVRE DE CAISSE",
        "date_document": timezone.now(),
    }
    filename = f"livre_caisse_{site.id}.pdf"
    return render_pdf("reports/livre_caisse.html", context, filename)


def _rapport_global_context(request):
    type_rapport = request.GET.get("type", "caisse")
    if type_rapport not in ("caisse", "stock"):
        raise Http404("Type de rapport inconnu.")

    sites = Site.objects.order_by("nom")
    site_id = request.GET.get("site", "")
    if site_id and not site_id.isdigit():
        raise Http404("Site inconnu.")
    site = get_object_or_404(sites, pk=site_id) if site_id else None
    debut_brut = request.GET.get("debut", "")
    fin_brut = request.GET.get("fin", "")
    debut = parse_date(debut_brut) if debut_brut else None
    fin = parse_date(fin_brut) if fin_brut else None
    if (debut_brut and debut is None) or (fin_brut and fin is None):
        raise Http404("Date de rapport invalide.")
    if debut and fin and debut > fin:
        raise Http404("La date de début doit précéder la date de fin.")

    if type_rapport == "caisse":
        lignes = TransactionMobileMoney.objects.select_related("site", "agent")
        if site:
            lignes = lignes.filter(site=site)
        if debut:
            lignes = lignes.filter(date_transaction__date__gte=debut)
        if fin:
            lignes = lignes.filter(date_transaction__date__lte=fin)
        lignes = lignes.order_by("-date_transaction")
        totaux = {
            ligne["devise"]: {
                "depots": ligne["depots"] or 0,
                "retraits": ligne["retraits"] or 0,
                "benefice": ligne["benefice"] or 0,
            }
            for ligne in lignes.order_by().values("devise").annotate(
                depots=Sum("montant", filter=Q(type_transaction="depot")),
                retraits=Sum("montant", filter=Q(type_transaction="retrait")),
                benefice=Sum("frais"),
            )
        }
    else:
        lignes = MouvementStock.objects.select_related(
            "produit", "produit__site", "utilisateur"
        ).annotate(valeur_ligne=F("quantite") * F("prix_unitaire"))
        if site:
            lignes = lignes.filter(produit__site=site)
        if debut:
            lignes = lignes.filter(date_mouvement__date__gte=debut)
        if fin:
            lignes = lignes.filter(date_mouvement__date__lte=fin)
        lignes = lignes.order_by("-date_mouvement")
        totaux = {
            "quantite": lignes.aggregate(total=Sum("quantite"))["total"] or 0,
            "valeur": lignes.aggregate(
                total=Sum(F("quantite") * F("prix_unitaire"))
            )["total"] or 0,
        }

    return {
        "type_rapport": type_rapport,
        "sites": sites,
        "site_selectionne": site,
        "debut": debut,
        "fin": fin,
        "lignes": lignes,
        "nombre_lignes": lignes.count(),
        "totaux": totaux,
        "date_generation": timezone.now(),
    }


@user_passes_test(lambda user: user.is_staff)
def rapports_administration(request):
    context = _rapport_global_context(request)
    page_size = request.GET.get("par_page", "25")
    if page_size not in ("10", "25", "50"):
        page_size = "25"
    page_obj = Paginator(context["lignes"], int(page_size)).get_page(request.GET.get("page"))
    querystring = request.GET.copy()
    querystring.pop("page", None)
    context.update({
        "page_obj": page_obj,
        "lignes": page_obj,
        "page_size": page_size,
        "querystring": querystring.urlencode(),
    })
    return render(
        request,
        "reports/administration_global.html",
        context,
    )


@user_passes_test(lambda user: user.is_staff)
def rapports_administration_pdf(request):
    context = _rapport_global_context(request)
    nom_site = context["site_selectionne"].id if context["site_selectionne"] else "tous"
    filename = f"rapport_{context['type_rapport']}_{nom_site}.pdf"
    context["mode_pdf"] = True
    return render_pdf("reports/administration_global_pdf.html", context, filename)
