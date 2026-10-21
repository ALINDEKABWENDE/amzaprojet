from decimal import Decimal

from django.db import models
from django.conf import settings
from core.models import Site


class Categorie(models.Model):
    nom = models.CharField(max_length=100)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="categories")

    class Meta:
        unique_together = ("nom", "site")
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.nom


class Produit(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="produits")
    categorie = models.ForeignKey(Categorie, on_delete=models.PROTECT, related_name="produits")
    nom = models.CharField(max_length=150)
    reference = models.CharField(max_length=50, blank=True)
    prix_achat = models.DecimalField(max_digits=12, decimal_places=2)
    prix_vente = models.DecimalField(max_digits=12, decimal_places=2)
    quantite_stock = models.PositiveIntegerField(default=0)
    seuil_alerte = models.PositiveIntegerField(default=5)

    def __str__(self):
        return f"{self.nom} ({self.site.nom})"

    @property
    def en_alerte(self):
        return self.quantite_stock <= self.seuil_alerte

    @property
    def valeur_stock(self):
        return self.quantite_stock * self.prix_achat


class Vente(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="ventes")
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    date_vente = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_vente"]

    @property
    def total(self):
        return sum((ligne.total for ligne in self.lignes.all()), Decimal("0.00"))

    def __str__(self):
        return f"Vente n°{self.id} - {self.site.nom}"


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="lignes")
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name="lignes_vente")
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["vente", "produit"], name="unique_produit_par_vente"),
        ]

    @property
    def total(self):
        return self.quantite * self.prix_unitaire


class MouvementStock(models.Model):
    """Trace chaque entrée/sortie -> sert de base au grand livre de stock."""

    TYPE_CHOICES = [
        ("entree", "Entrée"),
        ("sortie", "Sortie (vente)"),
        ("ajustement", "Ajustement"),
    ]

    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name="mouvements")
    vente = models.ForeignKey(
        Vente, on_delete=models.SET_NULL, null=True, blank=True, related_name="mouvements",
    )
    type_mouvement = models.CharField(max_length=15, choices=TYPE_CHOICES)
    quantite = models.IntegerField()
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    date_mouvement = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date_mouvement"]

    def __str__(self):
        return f"{self.get_type_mouvement_display()} - {self.produit.nom} x{self.quantite}"

    @property
    def total(self):
        return self.quantite * self.prix_unitaire
