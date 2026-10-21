from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from .models import Site


@login_required
def changer_site(request, site_id):
    """Permet à un vendeur rattaché à plusieurs sites de changer de site actif."""
    if request.user.is_staff:
        site = get_object_or_404(Site, id=site_id, actif=True)
    else:
        site = get_object_or_404(Site, id=site_id, vendeurs=request.user, actif=True)
    request.user.site_actif = site
    request.user.save(update_fields=["site_actif"])
    return redirect(request.user.dashboard_url_name)


@login_required
def site_en_attente(request):
    if request.user.is_staff and request.user.site_actif is None:
        return redirect("core:administration")
    return render(request, "core/site_en_attente.html", {"site": request.user.site_actif})


@user_passes_test(lambda user: user.is_staff)
def administration(request):
    sites = Site.objects.prefetch_related("vendeurs").order_by("actif", "nom")
    context = {
        "sites_en_attente": sites.filter(actif=False),
        "sites_actifs": sites.filter(actif=True),
        "nombre_sites": sites.count(),
    }
    return render(request, "core/administration.html", context)


@user_passes_test(lambda user: user.is_staff)
def site_approbation(request, site_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if request.POST.get("actif") not in ("true", "false"):
        messages.error(request, "Action invalide : choisissez une autorisation ou une suspension.")
        return redirect("core:administration")
    site = get_object_or_404(Site, pk=site_id)
    site.actif = request.POST.get("actif") == "true"
    site.save(update_fields=["actif"])
    statut = "autorisé" if site.actif else "suspendu"
    messages.success(request, f"Le site « {site.nom} » est maintenant {statut}.")
    return redirect("core:administration")
