from decimal import Decimal

from django import forms

from .models import TransactionMobileMoney


class SoldeOperateurForm(forms.Form):
    operateur = forms.ChoiceField(
        choices=TransactionMobileMoney.OPERATEUR_CHOICES,
        widget=forms.Select(attrs={"class": "form-select", "required": True}),
    )
    operateur_autre = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nom de l'opérateur",
        }),
    )
    devise = forms.ChoiceField(
        choices=TransactionMobileMoney.DEVISE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select", "required": True}),
    )
    montant = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01",
            "min": "0.01",
            "required": True,
        }),
    )

    def clean(self):
        cleaned = super().clean()
        operateur = cleaned.get("operateur")
        operateur_autre = (cleaned.get("operateur_autre") or "").strip()
        if operateur in ("autre_mobile", "autre_banque") and not operateur_autre:
            self.add_error("operateur_autre", "Précisez le nom de l'opérateur.")
        elif operateur not in ("autre_mobile", "autre_banque"):
            cleaned["operateur_autre"] = ""
        else:
            cleaned["operateur_autre"] = operateur_autre
        return cleaned

class TransactionForm(forms.ModelForm):
    montant = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01",
            "min": "0.01",
            "required": True,
        }),
    )
    frais = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        initial=Decimal("0"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )

    class Meta:
        model = TransactionMobileMoney
        fields = [
            "type_transaction", "operateur", "operateur_autre",
            "client_nom", "client_telephone", "devise", "montant", "frais",
        ]
        widgets = {
            "type_transaction": forms.HiddenInput(),
            "operateur": forms.Select(attrs={"class": "form-select"}),
            "devise": forms.Select(attrs={"class": "form-select", "required": True}),
            "operateur_autre": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Nom de l'opérateur",
            }),
            "client_nom": forms.TextInput(attrs={"class": "form-control", "required": True}),
            "client_telephone": forms.TextInput(attrs={"class": "form-control", "required": True}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "required": True}),
            "frais": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def clean(self):
        cleaned = super().clean()
        operateur = cleaned.get("operateur")
        operateur_autre = (cleaned.get("operateur_autre") or "").strip()
        if operateur in ("autre_mobile", "autre_banque") and not operateur_autre:
            self.add_error("operateur_autre", "Précisez le nom de l'opérateur.")
        elif operateur in ("autre_mobile", "autre_banque"):
            cleaned["operateur_autre"] = operateur_autre
        else:
            cleaned["operateur_autre"] = ""
        return cleaned

    def clean_frais(self):
        return self.cleaned_data.get("frais") or Decimal("0")


class TransactionModificationForm(forms.ModelForm):
    frais = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )

    class Meta:
        model = TransactionMobileMoney
        fields = ["client_nom", "client_telephone", "frais"]
        widgets = {
            "client_nom": forms.TextInput(attrs={"class": "form-control", "required": True}),
            "client_telephone": forms.TextInput(attrs={"class": "form-control", "required": True}),
            "frais": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        }
