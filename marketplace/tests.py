from datetime import timedelta
from hashlib import sha256

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"], "")
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
        group = Group.objects.create(name="Hirers")
        group.permissions.add(Permission.objects.get(content_type__app_label="marketplace", codename="change_job"))
        hirer.groups.add(group)
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
        self.assertContains(self.client.get(reverse("dashboard")), ">Your post<")
        self.client.force_login(another_hirer)
        self.assertNotContains(self.client.get(reverse("dashboard")), data["title"])
        another_hirer.groups.add(group)
        self.assertContains(self.client.get(reverse("dashboard")), data["title"])
        self.assertNotContains(self.client.get(reverse("dashboard")), ">Your post<")

    def test_freelancer_in_viewer_group_can_browse_jobs(self):
        hirer = User.objects.create_user(username="hirer", role=User.Role.HIRER)
        job = Job.objects.create(
            hirer=hirer, title="Fix a door", description="Replace a hinge.",
            location="Westlands", duration="2 hours", pay=2500, expectations="Bring a drill.",
        )
        freelancer = User.objects.create_user(username="fundi", role=User.Role.FREELANCER)
        FreelancerProfile.objects.create(user=freelancer, skills="Carpentry")
        self.client.force_login(freelancer)
        dashboard = reverse("dashboard")
        self.assertNotContains(self.client.get(dashboard), job.title)

        group = Group.objects.create(name="Freelancers")
        group.permissions.add(Permission.objects.get(content_type__app_label="marketplace", codename="view_job"))
        freelancer.groups.add(group)
        response = self.client.get(dashboard)
        self.assertContains(response, job.title)
        self.assertContains(self.client.get(reverse("job_detail", args=[job.pk])), "Bring a drill.")
        self.assertNotContains(response, "Post a job")
        self.assertEqual(self.client.get(reverse("create_job")).status_code, 403)

    def test_signup_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("signup_freelancer"), {}).status_code, 403)

    def test_login_rotates_session_and_logout_revokes_it(self):
        User.objects.create_user(username="hirer", password=self.password, role=User.Role.HIRER)
        anonymous = self.client.session
        anonymous["example"] = "value"
        anonymous.save()
        original_key = anonymous.session_key
        response = self.client.post(
            reverse("login_hirer"), {"username": "hirer", "password": self.password}
        )
        self.assertRedirects(response, reverse("dashboard"))
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertNotEqual(cookie.value, original_key)
        self.assertEqual(cookie["max-age"], "")
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertFalse(Session.objects.filter(session_key=original_key).exists())
        self.assertContains(self.client.get(reverse("dashboard")), "Welcome, hirer")

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.cookies[settings.SESSION_COOKIE_NAME] = cookie.value
        self.assertEqual(csrf_client.post(reverse("logout")).status_code, 403)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        self.assertFalse(Session.objects.filter(session_key=cookie.value).exists())
        self.assertRedirects(
            csrf_client.get(reverse("dashboard")),
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_remember_me_and_login_redirects(self):
        User.objects.create_user(username="hirer", password=self.password, role=User.Role.HIRER)
        login_url = reverse("login_hirer")
        job_url = reverse("create_job")
        self.assertContains(
            self.client.get(reverse("login"), {"next": job_url}), f"{login_url}?next={job_url}"
        )
        self.assertContains(self.client.get(login_url, {"next": job_url}), 'name="remember_me"')
        response = self.client.post(login_url, {
            "username": "hirer", "password": self.password, "remember_me": "on", "next": job_url,
        })
        self.assertRedirects(response, job_url)
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertAlmostEqual(int(cookie["max-age"]), settings.SESSION_COOKIE_AGE, delta=5)
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertRedirects(self.client.get(login_url, {"next": login_url}), reverse("dashboard"))

        Session.objects.filter(session_key=cookie.value).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        self.assertRedirects(
            self.client.get(reverse("dashboard")),
            f"{reverse('login')}?next={reverse('dashboard')}",
        )
        self.assertRedirects(
            self.client.post(login_url, {
                "username": "hirer", "password": self.password, "next": "https://example.com/",
            }),
            reverse("dashboard"),
        )

    def test_password_change_preserves_current_session_and_revokes_other_sessions(self):
        user = User.objects.create_user(
            username="hirer", password=self.password, role=User.Role.HIRER,
        )
        change_url = reverse("password_change")
        dashboard_url = reverse("dashboard")
        self.assertRedirects(self.client.get(change_url), f"{reverse('login')}?next={change_url}")
        other_browser = Client()
        self.client.force_login(user)
        other_browser.force_login(user)
        new_password = "woodwork-Cobalt-crib-479"
        response = self.client.post(change_url, {
            "old_password": self.password, "new_password1": new_password, "new_password2": new_password,
        }, follow=True)
        self.assertRedirects(response, dashboard_url)
        self.assertContains(response, "Your password was changed.")
        self.assertRedirects(
            other_browser.get(dashboard_url), f"{reverse('login')}?next={dashboard_url}"
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))
