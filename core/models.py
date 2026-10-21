from django.db import models


class Site(models.Model):
    """
    Représente un point physique (une quincaillerie ou un shop mobile money).
    Un vendeur peut être rattaché à un ou plusieurs sites.
    """

    TYPE_CHOICES = [
        ("quincaillerie", "Quincaillerie"),
        ("shop", "Shop Mobile Money"),
    ]

    nom = models.CharField(max_length=150)
    type_site = models.CharField(max_length=20, choices=TYPE_CHOICES)
    adresse = models.CharField(max_length=255, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    actif = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"

    def __str__(self):
        return f"{self.nom} ({self.get_type_site_display()})"
