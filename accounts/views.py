from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.models import Site
from .forms import InscriptionForm, ConnexionForm


def inscription(request):
    """
    Étape 1 : infos de base (nom, téléphone, mot de passe).
    Étape 2 (choix_profil) : quincaillerie ou shop.
    """
    if request.method == "POST":
        form = InscriptionForm(request.POST)
        if form.is_valid():
            utilisateur = form.save(commit=False)
            utilisateur.set_password(form.cleaned_data["password"])
            utilisateur.save()
            login(request, utilisateur)
            return redirect("accounts:choix_profil")
    else:
        form = InscriptionForm()
    return render(request, "accounts/inscription.html", {"form": form})


def choix_profil(request):
    """
    L'utilisateur choisit son activité (quincaillerie ou shop).

    Choisir un profil ne suffit pas : chaque tableau de bord (inventory,
    pos) exige un `request.user.site_actif` non nul, sinon il redirige
    vers     cette même page (voir inventory/views.py et pos/views.py). Le nouveau
    site est créé en attente et ne devient accessible qu'après approbation.
    """
    if request.method == "POST":
        profil = request.POST.get("profil")
        nom_site = request.POST.get("nom_site", "").strip()
        ville = request.POST.get("ville", "").strip()

        if profil not in ("quincaillerie", "shop"):
            messages.error(request, "Veuillez choisir une activité.")
        elif not nom_site:
            messages.error(request, "Veuillez donner un nom à votre site.")
        else:
            request.user.profil = profil
            request.user.save(update_fields=["profil"])

            site = Site.objects.create(nom=nom_site, type_site=profil, ville=ville)
            site.vendeurs.add(request.user)
            request.user.site_actif = site
            request.user.save(update_fields=["site_actif"])

            return redirect("core:site_en_attente")

    return render(request, "accounts/choix_profil.html")


def connexion_redirect(request):
    """Après login classique, redirige vers le bon tableau de bord."""
    if request.user.is_authenticated:
        if request.user.is_staff and request.user.site_actif is None:
            return redirect("core:administration")
        if request.user.site_actif and not request.user.site_actif.actif:
            return redirect("core:site_en_attente")
        return redirect(request.user.dashboard_url_name)
    return redirect(reverse("accounts:login"))


@require_http_methods(["GET", "POST"])
def deconnexion(request):
    # GET reste accepté pour les liens de déconnexion déjà ouverts dans le navigateur.
    logout(request)
    return redirect("accounts:login")
