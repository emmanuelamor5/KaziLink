from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from .models import FreelancerProfile, HirerAccessCode, Job, User


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "admin-demo-Cedar-536"
        cls.superuser = User.objects.create_superuser(
            username="siteadmin", password=cls.password,
        )
        cls.hirer = User.objects.create_user(username="hirer", role=User.Role.HIRER)

    def test_admin_login_and_freelancer_inline(self):
        freelancer = User.objects.create_user(username="fundi", role=User.Role.FREELANCER)
        profile = FreelancerProfile.objects.create(
            user=freelancer, skills="Carpentry", available=True,
            document_type=FreelancerProfile.DocumentType.PASSPORT,
            document_hash="hidden-document-hash",
        )
        code = HirerAccessCode.objects.create(digest="hidden-code-digest")
        self.client.force_login(self.hirer)
        self.assertRedirects(
            self.client.get(reverse("admin:index")), "/admin/login/?next=/admin/",
        )
        self.client.logout()
        self.assertRedirects(self.client.post(reverse("admin:login"), {
            "username": self.superuser.username, "password": self.password,
            "next": reverse("admin:index"),
        }), reverse("admin:index"))
        self.assertContains(self.client.get(reverse("admin:index")), "KaziLink Administration")
        account_url = reverse("admin:marketplace_user_change", args=[freelancer.pk])
        account = self.client.get(account_url)
        self.assertContains(account, "Carpentry")
        self.assertContains(account, "Passport")
        self.assertNotContains(account, "hidden-document-hash")
        self.assertRedirects(self.client.post(account_url, {
            "username": freelancer.username, "is_active": "on", "role": User.Role.FREELANCER,
            "date_joined_0": "2026-11-28", "date_joined_1": "09:00:00",
            "freelancer_profile-TOTAL_FORMS": "1", "freelancer_profile-INITIAL_FORMS": "1",
            "freelancer_profile-0-id": profile.pk, "freelancer_profile-0-user": freelancer.pk,
            "freelancer_profile-0-skills": "Furniture repair",
        }), reverse("admin:marketplace_user_changelist"))
        profile.refresh_from_db()
        self.assertEqual(profile.skills, "Furniture repair")
        self.assertFalse(profile.available)
        code_detail = self.client.get(
            reverse("admin:marketplace_hireraccesscode_change", args=[code.pk])
        )
        self.assertContains(code_detail, "Issued at")
        self.assertNotContains(code_detail, "hidden-code-digest")
        self.assertEqual(
            self.client.get(reverse("admin:marketplace_hireraccesscode_add")).status_code, 403,
        )

    def test_superuser_can_change_roles_and_reuse_freelancer_profile(self):
        self.client.force_login(self.superuser)
        account_url = reverse("admin:marketplace_user_change", args=[self.hirer.pk])
        users = reverse("admin:marketplace_user_changelist")
        data = {
            "username": self.hirer.username, "is_active": "on", "role": User.Role.FREELANCER,
            "date_joined_0": "2026-11-28", "date_joined_1": "09:00:00",
        }
        self.assertContains(self.client.get(account_url), 'name="role"')
        response = self.client.post(account_url, data)
        self.assertContains(response, "This field is required when assigning the Freelancer role.")
        self.hirer.refresh_from_db()
        self.assertEqual(self.hirer.role, User.Role.HIRER)
        self.assertFalse(FreelancerProfile.objects.filter(user=self.hirer).exists())

        self.assertRedirects(self.client.post(account_url, {
            **data,
            "new_freelancer_skills": "Painting", "new_freelancer_available": "on",
            "new_freelancer_document_type": FreelancerProfile.DocumentType.PASSPORT,
            "new_freelancer_document_number": "DEMO12345",
        }), users)
        self.hirer.refresh_from_db()
        self.assertEqual(self.hirer.role, User.Role.FREELANCER)
        profile = FreelancerProfile.objects.get(user=self.hirer)
        self.assertTrue(check_password("DEMO12345", profile.document_hash))

        self.assertRedirects(self.client.post(account_url, {
            **data, "role": User.Role.HIRER,
            "freelancer_profile-TOTAL_FORMS": "1", "freelancer_profile-INITIAL_FORMS": "1",
            "freelancer_profile-0-id": profile.pk, "freelancer_profile-0-user": self.hirer.pk,
            "freelancer_profile-0-skills": profile.skills, "freelancer_profile-0-available": "on",
        }), users)
        self.hirer.refresh_from_db()
        self.assertEqual(self.hirer.role, User.Role.HIRER)
        self.assertRedirects(self.client.post(account_url, data), users)
        self.assertEqual(FreelancerProfile.objects.get(user=self.hirer).pk, profile.pk)

        self.client.force_login(self.hirer)
        self.assertContains(self.client.get(reverse("dashboard")), "Painting")
        self.assertEqual(self.client.get(reverse("create_job")).status_code, 403)

    def test_superuser_can_manage_jobs(self):
        self.client.force_login(self.superuser)
        data = {
            "title": "Paint a gate", "hirer": self.hirer.pk, "description": "Paint two coats.",
            "location": "Westlands", "duration": "2 hours", "pay": "2000",
            "expectations": "Bring a brush.",
        }
        listing = reverse("admin:marketplace_job_changelist")
        self.assertRedirects(
            self.client.post(reverse("admin:marketplace_job_add"), data), listing,
        )
        job = Job.objects.get()
        self.assertContains(self.client.get(listing, {"q": "Westlands"}), job.title)
        self.assertNotContains(self.client.get(listing, {"q": "Kisumu"}), job.title)
        self.assertRedirects(
            self.client.post(
                reverse("admin:marketplace_job_change", args=[job.pk]),
                {**data, "title": "Paint two gates"},
            ),
            listing,
        )
        job.refresh_from_db()
        self.assertEqual(job.title, "Paint two gates")
        self.assertRedirects(
            self.client.post(reverse("admin:marketplace_job_delete", args=[job.pk]), {"post": "yes"}),
            listing,
        )
        self.assertFalse(Job.objects.exists())

    def test_staff_group_permissions_control_admin_access(self):
        reviewer = User.objects.create_user(username="reviewer", is_staff=True)
        group = Group.objects.create(name="Job reviewers")
        group.permissions.add(Permission.objects.get(
            content_type__app_label="marketplace", codename="view_job",
        ))
        reviewer.groups.add(group)
        self.client.force_login(reviewer)

        self.assertEqual(self.client.get(reverse("admin:marketplace_job_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:marketplace_job_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:marketplace_user_changelist")).status_code, 403)

        group.permissions.add(*Permission.objects.filter(
            codename__in=("change_user", "change_group"),
            content_type__app_label__in=("marketplace", "auth"),
        ))
        user_edit = reverse("admin:marketplace_user_change", args=[reviewer.pk])
        group_edit = reverse("admin:auth_group_change", args=[group.pk])
        self.assertEqual(self.client.post(user_edit, {"is_superuser": "on"}).status_code, 403)
        self.assertEqual(self.client.post(group_edit, {"name": "Job reviewers"}).status_code, 403)

    def test_group_actions_add_matching_roles_and_preserve_memberships(self):
        freelancers = Group.objects.create(name="Freelancers")
        hirers = Group.objects.create(name="Hirers")
        other = Group.objects.create(name="Other")
        freelancer = User.objects.create_user(username="fundi", role=User.Role.FREELANCER)
        second = User.objects.create_user(username="fundi2", role=User.Role.FREELANCER)
        freelancer.groups.add(other)
        self.client.force_login(self.superuser)
        groups_list = reverse("admin:auth_group_changelist")

        response = self.client.post(groups_list, {
            "action": "add_all_freelancers", "_selected_action": [freelancers.pk, hirers.pk],
        }, follow=True)
        self.assertContains(response, "Select exactly one destination group.")
        self.assertFalse(freelancers.user_set.exists())
        self.assertFalse(hirers.user_set.exists())

        for group, action in ((freelancers, "add_all_freelancers"), (hirers, "add_all_hirers")):
            for _ in range(2):
                self.assertRedirects(self.client.post(groups_list, {
                    "action": action, "_selected_action": group.pk,
                }), groups_list)

        self.assertCountEqual(freelancers.user_set.all(), [freelancer, second])
        self.assertCountEqual(hirers.user_set.all(), [self.hirer])
        self.assertCountEqual(other.user_set.all(), [freelancer])
