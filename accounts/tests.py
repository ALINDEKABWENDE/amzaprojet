from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse


class LoginPageTests(TestCase):
    def test_login_page_renders_the_updated_access_form(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="app-body login-page"')
        self.assertContains(response, 'class="navbar navbar-expand-xl app-navbar mb-4"')
        self.assertContains(response, 'class="app-footer"')
        self.assertContains(response, "Gérez votre activité en toute simplicité.")
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'class="login-password-toggle"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_invalid_login_keeps_the_error_feedback_visible(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "inconnu", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identifiants incorrects.")


class RegistrationPageTests(TestCase):
    def test_registration_page_shows_profile_creation_form(self):
        response = self.client.get(reverse("accounts:inscription"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="app-body register-page"')
        self.assertContains(response, 'class="navbar navbar-expand-xl app-navbar mb-4"')
        self.assertContains(response, 'class="app-footer"')
        self.assertContains(response, "Un espace de gestion à votre image.")
        self.assertContains(response, "Étape 1 sur 2")
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="tel"')
        self.assertContains(response, 'autocomplete="new-password"')
        self.assertContains(response, 'class="login-password-toggle"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_registration_keeps_password_confirmation_validation(self):
        response = self.client.post(
            reverse("accounts:inscription"),
            {
                "username": "nouveau",
                "first_name": "Nouveau",
                "last_name": "Compte",
                "telephone": "0999000011",
                "password": "mot-de-passe-1",
                "password_confirm": "mot-de-passe-2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les mots de passe ne correspondent pas.")


class CreateSuperuserTests(TestCase):
    @patch.dict("os.environ", {"DJANGO_SUPERUSER_PASSWORD": "test-admin-password"})
    def test_createsuperuser_prompts_for_unique_phone_and_profile(self):
        output = StringIO()

        call_command(
            "createsuperuser",
            "--noinput",
            username="admin-terminal",
            email="admin-terminal@example.com",
            telephone="0999000099",
            profil="shop",
            stdout=output,
        )

        user = get_user_model().objects.get(username="admin-terminal")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.telephone, "0999000099")
        self.assertEqual(user.profil, "shop")
