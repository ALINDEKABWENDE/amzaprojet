from django import forms
from .models import Produit, Categorie


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = [
            "categorie", "nom", "reference", "prix_achat", "prix_vente",
            "quantite_stock", "seuil_alerte",
        ]
        widgets = {
            "categorie": forms.Select(attrs={"class": "form-select"}),
            "nom": forms.TextInput(attrs={"class": "form-control", "required": True}),
            "reference": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optionnel"}),
            "prix_achat": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "required": True}),
            "prix_vente": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "required": True}),
            "quantite_stock": forms.NumberInput(attrs={"class": "form-control"}),
            "seuil_alerte": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        if site is not None:
            self.fields["categorie"].queryset = Categorie.objects.filter(site=site)

    def clean(self):
        cleaned = super().clean()
        prix_achat = cleaned.get("prix_achat")
        prix_vente = cleaned.get("prix_vente")
        if prix_achat is not None and prix_vente is not None and prix_vente < prix_achat:
            self.add_error("prix_vente", "Le prix de vente est inférieur au prix d'achat.")
        return cleaned


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["nom"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex : Outillage, Plomberie..."}),
        }
