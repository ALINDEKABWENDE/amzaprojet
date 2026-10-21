from django.conf import settings
from django.db import models
from core.models import Site


DEVISE_OPERATEUR_CHOICES = [
    ("USD", "Dollar américain (USD)"),
    ("CDF", "Franc congolais (CDF)"),
]

OPERATEURS_CHOICES = [
    ("Mobile Money", (
        ("mpesa", "M-Pesa (Vodacom)"),
        ("airtel_money", "Airtel Money"),
        ("orange_money", "Orange Money"),
        ("afrimoney", "Afrimoney (Africell)"),
        ("autre_mobile", "Autre mobile money"),
    )),
    ("Banque", (
        ("equity", "Equity BCDC"),
        ("rawbank", "Rawbank"),
        ("tmb", "Trust Merchant Bank (TMB)"),
        ("fbn", "FBNBank"),
        ("autre_banque", "Autre banque"),
    )),
]


class Caisse(models.Model):
    """Solde de caisse courant pour un site donné."""

    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="caisse")
    solde = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    solde_cdf = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    derniere_maj = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Caisse {self.site.nom} : {self.solde}"


class SoldeOperateur(models.Model):
    """Solde virtuel disponible, distinct pour chaque opérateur et devise."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="soldes_operateurs")
    operateur = models.CharField(max_length=20, choices=OPERATEURS_CHOICES)
    operateur_autre = models.CharField(max_length=100, blank=True)
    devise = models.CharField(max_length=3, choices=DEVISE_OPERATEUR_CHOICES)
    solde = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    derniere_maj = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "operateur", "operateur_autre", "devise"],
                name="unique_solde_operateur_site_devise",
            ),
        ]
        ordering = ["operateur", "operateur_autre", "devise"]

    @property
    def operateur_affiche(self):
        if self.operateur in ("autre_mobile", "autre_banque") and self.operateur_autre:
            return self.operateur_autre
        return self.get_operateur_display()

    def __str__(self):
        return f"{self.operateur_affiche} ({self.devise}) : {self.solde}"


class TransactionMobileMoney(models.Model):
    DEVISE_CHOICES = DEVISE_OPERATEUR_CHOICES

    TYPE_CHOICES = [
        ("depot", "Dépôt"),
        ("retrait", "Retrait"),
    ]

    # "autre_mobile" / "autre_banque" couvrent les opérateurs non listés.
    OPERATEUR_CHOICES = OPERATEURS_CHOICES

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="transactions")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    type_transaction = models.CharField(max_length=10, choices=TYPE_CHOICES)
    operateur = models.CharField(max_length=20, choices=OPERATEUR_CHOICES, default="mpesa")
    operateur_autre = models.CharField(
        max_length=100, blank=True,
        help_text="Nom de l'opérateur si 'Autre mobile money' / 'Autre banque' est sélectionné.",
    )
    client_nom = models.CharField(max_length=150)
    client_telephone = models.CharField(max_length=20)
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    frais = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    devise = models.CharField(max_length=3, choices=DEVISE_CHOICES, default="USD")
    date_transaction = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_transaction"]

    @property
    def operateur_categorie(self):
        """'banque' ou 'mobile' — utilisé pour les badges et les filtres."""
        return "banque" if self.operateur in ("equity", "rawbank", "tmb", "fbn", "autre_banque") else "mobile"

    @property
    def operateur_affiche(self):
        if self.operateur in ("autre_mobile", "autre_banque") and self.operateur_autre:
            return self.operateur_autre
        return self.get_operateur_display()

    def __str__(self):
        return f"{self.get_type_transaction_display()} - {self.montant} ({self.client_nom})"

    def appliquer_a_la_caisse(self):
        """Met à jour le solde de la caisse selon le type de transaction."""
        caisse, _ = Caisse.objects.get_or_create(site=self.site)
        champ_solde = "solde" if self.devise == "USD" else "solde_cdf"
        if self.type_transaction == "depot":
            setattr(caisse, champ_solde, getattr(caisse, champ_solde) - self.montant)
        else:
            setattr(caisse, champ_solde, getattr(caisse, champ_solde) + self.montant)
        caisse.save(update_fields=[champ_solde])
