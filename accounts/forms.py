from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Utilisateur


class InscriptionForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control login-input",
            "placeholder": "Choisissez un mot de passe",
            "autocomplete": "new-password",
        }),
        label="Mot de passe",
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control login-input",
            "placeholder": "Saisissez à nouveau le mot de passe",
            "autocomplete": "new-password",
        }),
        label="Confirmer le mot de passe",
    )

    class Meta:
        model = Utilisateur
        fields = ["username", "first_name", "last_name", "telephone"]
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-control login-input",
                "placeholder": "Choisissez un nom d'utilisateur",
                "autocomplete": "username",
                "autofocus": True,
            }),
            "first_name": forms.TextInput(attrs={
                "class": "form-control login-input",
                "placeholder": "Votre prénom",
                "autocomplete": "given-name",
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-control login-input",
                "placeholder": "Votre nom",
                "autocomplete": "family-name",
            }),
            "telephone": forms.TextInput(attrs={
                "class": "form-control login-input",
                "placeholder": "Votre numéro de téléphone",
                "autocomplete": "tel",
                "inputmode": "tel",
            }),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password_confirm"):
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned


class ConnexionForm(AuthenticationForm):
    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={
            "class": "form-control login-input",
            "placeholder": "Saisissez votre nom d'utilisateur",
            "autocomplete": "username",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control login-input",
            "placeholder": "Saisissez votre mot de passe",
            "autocomplete": "current-password",
        }),
        label="Mot de passe",
    )
