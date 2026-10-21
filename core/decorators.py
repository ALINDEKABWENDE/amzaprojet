from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def site_actif_requis(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        site = request.user.site_actif
        if site is None:
            return redirect("accounts:choix_profil")
        if not site.actif:
            messages.warning(
                request,
                "Votre site attend l’autorisation d’un administrateur. "
                "Vous pourrez accéder à l’application après son approbation.",
            )
            return redirect("core:site_en_attente")
        return view_func(request, *args, **kwargs)

    return wrapped
