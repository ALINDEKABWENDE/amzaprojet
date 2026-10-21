from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .forms import ConnexionForm

app_name = "accounts"

urlpatterns = [
    path("inscription/", views.inscription, name="inscription"),
    path("choix-profil/", views.choix_profil, name="choix_profil"),
    path(
        "connexion/",
        auth_views.LoginView.as_view(
            template_name="accounts/connexion.html",
            authentication_form=ConnexionForm,
        ),
        name="login",
    ),
    path("deconnexion/", views.deconnexion, name="logout"),
    path("redirection/", views.connexion_redirect, name="redirect"),
]
