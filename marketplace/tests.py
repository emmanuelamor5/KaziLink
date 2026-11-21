from hashlib import sha256

from django.contrib.auth.hashers import check_password
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import FreelancerProfile, HirerAccessCode, Job, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MarketplaceTests(TestCase):
    password = "odds-Pine-plateau-317"
    code = "0123456789ABCDEF" * 2

    def signup_data(self, username):
        return {
            "first_name": "Demo", "last_name": "User", "username": username,
            "email": f"{username}@example.com", "location": "Westlands",
            "password1": self.password, "password2": self.password,
        }

    def issue_code(self):
        return HirerAccessCode.objects.create(digest=sha256(self.code.encode()).hexdigest())

    def test_landing_and_role_selection(self):
        self.assertContains(self.client.get(reverse("home")), "Join as a freelancer")
        self.assertContains(self.client.get(reverse("signup")), reverse("signup_hirer"))
        self.assertContains(self.client.get(reverse("login")), reverse("login_freelancer"))

    def test_freelancer_registration_and_role_login(self):
        signup = reverse("signup_freelancer")
        data = {
            **self.signup_data("fundi"), "skills": "Carpentry", "available": "on",
            "document_type": "national_id", "document_number": "DEMO12345",
        }
        invalid = self.client.post(signup, {**data, "document_number": "??"})
        self.assertContains(invalid, "Enter 5 to 24 letters or digits.")
        self.assertFalse(User.objects.exists())

        response = self.client.post(signup, data)
        self.assertRedirects(response, reverse("dashboard"))
        profile = FreelancerProfile.objects.get(user__username="fundi")
        self.assertTrue(check_password(data["document_number"], profile.document_hash))
        self.assertContains(self.client.get(reverse("dashboard")), "Carpentry")
        self.assertNotContains(self.client.get(reverse("dashboard")), data["document_number"])
        self.assertEqual(self.client.get(reverse("create_job")).status_code, 403)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))

        credentials = {"username": "fundi", "password": self.password}
        self.assertEqual(self.client.post(reverse("login_hirer"), credentials).status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.client.post(reverse("login_freelancer"), credentials), reverse("dashboard")
        )

    def test_hirer_id_is_required_and_single_use(self):
        code = self.issue_code()
        signup = reverse("signup_hirer")
        data = self.signup_data("hirer")
        self.assertContains(
            self.client.post(signup, {**data, "requirement_id": "0" * 32}),
            "Enter a valid, unused hirer requirement ID.",
        )
        self.assertFalse(User.objects.exists())
        self.assertRedirects(
            self.client.post(signup, {**data, "requirement_id": self.code.lower()}),
            reverse("dashboard"),
        )
        code.refresh_from_db()
        self.assertIsNotNone(code.redeemed_at)
        self.client.post(reverse("logout"))
        self.assertContains(
            self.client.post(signup, {**self.signup_data("second"), "requirement_id": self.code}),
            "Enter a valid, unused hirer requirement ID.",
        )
        self.assertFalse(User.objects.filter(username="second").exists())
        self.assertRedirects(
            self.client.post(reverse("login_hirer"), {"username": "hirer", "password": self.password}),
            reverse("dashboard"),
        )

    def test_job_form_checks_authentication_and_saves_to_signed_in_hirer(self):
        create_job = reverse("create_job")
        self.assertRedirects(self.client.get(create_job), f"{reverse('login')}?next={create_job}")
        hirer = User.objects.create_user(username="hirer", role=User.Role.HIRER)
        another_hirer = User.objects.create_user(username="other", role=User.Role.HIRER)
        self.client.force_login(hirer)
        data = {
            "title": "Repair a shelf", "description": "Fix a damaged bracket.",
            "location": "Westlands", "duration": "2 hours", "pay": "2500",
            "expectations": "Bring a drill.", "hirer": another_hirer.pk,
        }
        self.assertEqual(self.client.post(create_job, {**data, "pay": "0"}).status_code, 200)
        self.assertFalse(Job.objects.exists())
        self.assertRedirects(self.client.post(create_job, data), reverse("dashboard"))
        self.assertEqual(Job.objects.get().hirer, hirer)
        self.assertContains(self.client.get(reverse("dashboard")), data["title"])
        self.client.force_login(another_hirer)
        self.assertNotContains(self.client.get(reverse("dashboard")), data["title"])

    def test_signup_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("signup_freelancer"), {}).status_code, 403)
