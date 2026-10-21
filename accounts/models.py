from django.contrib.auth.models import AbstractUser
from django.db import models
from core.models import Site


class Utilisateur(AbstractUser):
    """
    Utilisateur personnalisé. Le champ profil détermine vers quel
    tableau de bord il sera redirigé après connexion.
    """

    PROFIL_CHOICES = [
        ("quincaillerie", "Quincaillerie"),
        ("shop", "Shop Mobile Money"),
    ]

    REQUIRED_FIELDS = ["email", "telephone", "profil"]

    telephone = models.CharField(max_length=20, unique=True)
    profil = models.CharField(max_length=20, choices=PROFIL_CHOICES)
    sites = models.ManyToManyField(Site, related_name="vendeurs", blank=True)
    site_actif = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Site actuellement sélectionné par le vendeur",
    )

    def __str__(self):
        return f"{self.username} ({self.get_profil_display()})"

    @property
    def activite_active(self):
        """Activité du site courant pour le personnel, profil sinon."""
        if self.is_staff and self.site_actif_id:
            return self.site_actif.type_site
        return self.profil

    @property
    def dashboard_url_name(self):
        """Nom de l'URL vers laquelle rediriger après connexion."""
        return "inventory:dashboard" if self.activite_active == "quincaillerie" else "pos:dashboard"
