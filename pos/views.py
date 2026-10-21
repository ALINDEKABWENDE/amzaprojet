from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction as db_transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.decorators import site_actif_requis
from .forms import SoldeOperateurForm, TransactionForm, TransactionModificationForm
from .models import Caisse, SoldeOperateur, TransactionMobileMoney


def _filtrer_transactions(request, queryset):
    """Filtres communs au dashboard et à l'historique : type, opérateur, dates, recherche."""
    type_transaction = request.GET.get("type", "")
    operateur = request.GET.get("operateur", "")
    devise = request.GET.get("devise", "")
    debut = request.GET.get("debut", "")
    fin = request.GET.get("fin", "")
    recherche = request.GET.get("q", "").strip()

    if type_transaction in ("depot", "retrait"):
        queryset = queryset.filter(type_transaction=type_transaction)
    if operateur:
        queryset = queryset.filter(operateur=operateur)
    if devise in ("USD", "CDF"):
        queryset = queryset.filter(devise=devise)
    if debut:
        d = parse_date(debut)
        if d:
            queryset = queryset.filter(date_transaction__date__gte=d)
    if fin:
        f = parse_date(fin)
        if f:
            queryset = queryset.filter(date_transaction__date__lte=f)
    if recherche:
        queryset = queryset.filter(client_nom__icontains=recherche) | queryset.filter(
            client_telephone__icontains=recherche
        )

    filtres = {
        "type": type_transaction, "operateur": operateur,
        "devise": devise, "debut": debut, "fin": fin, "q": recherche,
    }
    return queryset, filtres


@site_actif_requis
def dashboard(request):
    site = request.user.site_actif

    caisse, _ = Caisse.objects.get_or_create(site=site)
    aujourdhui = timezone.localdate()
    debut_defaut = aujourdhui - timedelta(days=6)
    debut = parse_date(request.GET.get("debut", "")) or debut_defaut
    fin = parse_date(request.GET.get("fin", "")) or aujourdhui
    if debut > fin:
        debut, fin = fin, debut

    transactions_jour = TransactionMobileMoney.objects.filter(
        site=site,
        date_transaction__date__gte=debut,
        date_transaction__date__lte=fin,
    )

    operateur = request.GET.get("operateur", "")
    if operateur:
        transactions_jour = transactions_jour.filter(operateur=operateur)

    devise = request.GET.get("devise", "")
    if devise in ("USD", "CDF"):
        transactions_jour = transactions_jour.filter(devise=devise)

    totaux_par_devise = list(
        transactions_jour.values("devise").annotate(
            depots=Sum("montant", filter=Q(type_transaction="depot")),
            retraits=Sum("montant", filter=Q(type_transaction="retrait")),
            benefice=Sum("frais"),
            nombre=Count("id"),
        ).order_by("devise")
    )
    totaux = {
        devise_code: {
            "depots": ligne["depots"] or 0,
            "retraits": ligne["retraits"] or 0,
            "benefice": ligne["benefice"] or 0,
            "nombre": ligne["nombre"],
        }
        for devise_code, ligne in (
            (ligne["devise"], ligne) for ligne in totaux_par_devise
        )
    }
    totaux_usd = totaux.get("USD", {})
    total_depots = totaux_usd.get("depots", 0)
    total_retraits = totaux_usd.get("retraits", 0)
    benefice = totaux_usd.get("benefice", 0)
    nombre_transactions = sum(ligne["nombre"] for ligne in totaux_par_devise)
    transactions_jour = transactions_jour.order_by("-date_transaction")

    transactions_par_jour = transactions_jour.annotate(
        jour=TruncDate("date_transaction")
    ).values("jour", "type_transaction", "devise").annotate(total=Sum("montant")).order_by("jour")
    dates_transactions = sorted({ligne["jour"] for ligne in transactions_par_jour})
    montants_par_jour = defaultdict(dict)
    for ligne in transactions_par_jour:
        montants_par_jour[ligne["jour"]][
            (ligne["devise"], ligne["type_transaction"])
        ] = ligne["total"]

    page_size_choices = (10, 25, 50)
    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10
    if page_size not in page_size_choices:
        page_size = 10

    paginator = Paginator(transactions_jour, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    querystring = request.GET.copy()
    querystring.pop("page", None)
    report_querystring = request.GET.copy()
    report_querystring.pop("page", None)
    report_querystring.pop("q", None)
    report_querystring.pop("type", None)
    report_querystring["debut"] = debut.isoformat()
    report_querystring["fin"] = fin.isoformat()

    context = {
        "site": site,
        "caisse": caisse,
        "soldes_operateurs": SoldeOperateur.objects.filter(site=site),
        "transactions": page_obj,
        "page_obj": page_obj,
        "total_depots": total_depots,
        "total_retraits": total_retraits,
        "benefice": benefice,
        "total_depots_cdf": totaux.get("CDF", {}).get("depots", 0),
        "total_retraits_cdf": totaux.get("CDF", {}).get("retraits", 0),
        "benefice_cdf": totaux.get("CDF", {}).get("benefice", 0),
        "nombre_transactions": nombre_transactions,
        "debut_stats": debut.isoformat(),
        "fin_stats": fin.isoformat(),
        "labels_transactions": [jour.strftime("%d/%m") for jour in dates_transactions],
        "depots_par_jour": [float(montants_par_jour[jour].get(("USD", "depot"), 0)) for jour in dates_transactions],
        "retraits_par_jour": [float(montants_par_jour[jour].get(("USD", "retrait"), 0)) for jour in dates_transactions],
        "depots_cdf_par_jour": [float(montants_par_jour[jour].get(("CDF", "depot"), 0)) for jour in dates_transactions],
        "retraits_cdf_par_jour": [float(montants_par_jour[jour].get(("CDF", "retrait"), 0)) for jour in dates_transactions],
        "operateur_choices": TransactionMobileMoney.OPERATEUR_CHOICES,
        "operateur_actif": operateur,
        "devise_choices": TransactionMobileMoney.DEVISE_CHOICES,
        "devise_active": devise,
        "report_querystring": report_querystring.urlencode(),
        "nombre_transactions_usd": totaux_usd.get("nombre", 0),
        "nombre_transactions_cdf": totaux.get("CDF", {}).get("nombre", 0),
        "querystring": querystring.urlencode(),
        "page_size": page_size,
        "page_size_choices": page_size_choices,
    }
    return render(request, "pos/dashboard.html", context)


@site_actif_requis
def nouvelle_transaction(request):
    site = request.user.site_actif

    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.site = site
            transaction.agent = request.user

            with db_transaction.atomic():
                solde, _ = SoldeOperateur.objects.get_or_create(
                    site=site,
                    operateur=transaction.operateur,
                    operateur_autre=transaction.operateur_autre,
                    devise=transaction.devise,
                )
                if transaction.type_transaction == "depot":
                    debited = SoldeOperateur.objects.filter(
                        pk=solde.pk,
                        solde__gte=transaction.montant,
                    ).update(solde=F("solde") - transaction.montant)
                    if not debited:
                        solde.refresh_from_db()
                        messages.error(
                            request,
                            f"Solde virtuel insuffisant chez {solde.operateur_affiche} "
                            f"({solde.devise}) : {solde.solde:.2f} disponible. "
                            "Demandez à un administrateur de définir ou réapprovisionner ce solde.",
                        )
                        return redirect("pos:dashboard")
                else:
                    SoldeOperateur.objects.filter(pk=solde.pk).update(
                        solde=F("solde") + transaction.montant
                    )

                transaction.save()
                transaction.appliquer_a_la_caisse()

            messages.success(request, "Transaction enregistrée avec succès.")
            return redirect("pos:dashboard")
        messages.error(request, f"Transaction invalide : {form.errors.as_text()}")

    return redirect("pos:dashboard")


@site_actif_requis
def approvisionner_solde_operateur(request):
    site = request.user.site_actif
    if not request.user.is_staff:
        messages.error(
            request,
            "Seul un administrateur peut définir ou réapprovisionner un solde virtuel.",
        )
        return redirect("pos:dashboard")
    if request.method != "POST":
        return redirect("pos:dashboard")

    form = SoldeOperateurForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Approvisionnement invalide : {form.errors.as_text()}")
        return redirect("pos:dashboard")

    with db_transaction.atomic():
        solde, _ = SoldeOperateur.objects.get_or_create(
            site=site,
            operateur=form.cleaned_data["operateur"],
            operateur_autre=form.cleaned_data["operateur_autre"],
            devise=form.cleaned_data["devise"],
        )
        SoldeOperateur.objects.filter(pk=solde.pk).update(
            solde=F("solde") + form.cleaned_data["montant"]
        )

    messages.success(
        request,
        f"Solde virtuel approvisionné pour {solde.operateur_affiche} ({solde.devise}).",
    )
    return redirect("pos:dashboard")


@site_actif_requis
def historique(request):
    """Historique complet, paginé et filtrable, des dépôts/retraits mobile money."""
    site = request.user.site_actif
    transactions = TransactionMobileMoney.objects.filter(site=site).select_related("agent")
    transactions, filtres = _filtrer_transactions(request, transactions)
    transactions = transactions.order_by("-date_transaction")

    totaux_par_devise = {}
    for ligne in transactions.order_by().values("devise", "type_transaction").annotate(total=Sum("montant")):
        totaux_par_devise.setdefault(ligne["devise"], {})[ligne["type_transaction"]] = ligne["total"]

    paginator = Paginator(transactions, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    querystring = request.GET.copy()
    querystring.pop("page", None)

    context = {
        "site": site,
        "transactions": page_obj,
        "page_obj": page_obj,
        "filtres": filtres,
        "operateur_choices": TransactionMobileMoney.OPERATEUR_CHOICES,
        "devise_choices": TransactionMobileMoney.DEVISE_CHOICES,
        "totaux_par_devise": totaux_par_devise,
        "querystring": querystring.urlencode(),
    }
    return render(request, "pos/historique.html", context)


@site_actif_requis
def transaction_modifier(request, transaction_id):
    transaction = get_object_or_404(
        TransactionMobileMoney, id=transaction_id, site=request.user.site_actif
    )
    if request.method == "POST":
        form = TransactionModificationForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, "Transaction mise à jour.")
            return redirect("pos:historique")
    else:
        form = TransactionModificationForm(instance=transaction)
    return render(request, "pos/transaction_form.html", {"form": form, "transaction": transaction})
