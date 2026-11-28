from datetime import timedelta

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import FreelancerProfile, Job, JobApplication, JobView, User


class HiringWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        viewer_permission = Permission.objects.get(
            content_type__app_label="marketplace", codename="view_job",
        )
        cls.hirer = User.objects.create_user(username="hirer", first_name="Kamau", role=User.Role.HIRER)
        cls.other_hirer = User.objects.create_user(username="other-hirer", role=User.Role.HIRER)
        cls.freelancer = User.objects.create_user(
            username="fundi", first_name="Amina", email="amina@example.com", role=User.Role.FREELANCER,
        )
        FreelancerProfile.objects.create(
            user=cls.freelancer, skills="Cabinetmaking", available=True,
        )
        cls.freelancer.user_permissions.add(viewer_permission)
        cls.other_hirer.user_permissions.add(viewer_permission)
        cls.job = Job.objects.create(
            hirer=cls.hirer, title="Repair a cabinet", description="Replace a damaged hinge.",
            location="Kisumu", duration="2 hours", pay=2500, expectations="Bring a screwdriver.",
        )

    def test_hiring_flow_from_unique_view_to_accepted_invitation_and_removal(self):
        hirer_client = Client()
        hirer_client.force_login(self.hirer)
        self.client.force_login(self.freelancer)
        detail = reverse("job_detail", args=[self.job.pk])
        apply_url = reverse("apply_for_job", args=[self.job.pk])
        review = reverse("job_review", args=[self.job.pk])
        remove = reverse("delete_listing", args=[self.job.pk])
        self.assertContains(self.client.get(reverse("dashboard"), {"q": "screwdriver"}), detail)
        self.assertNotContains(self.client.get(reverse("dashboard"), {"q": "plumbing"}), self.job.title)
        self.assertContains(self.client.get(detail), "Hiring · Kamau")
        self.assertContains(self.client.get(detail), apply_url)
        self.assertEqual(hirer_client.get(detail).status_code, 200)
        self.assertEqual(JobView.objects.filter(job=self.job).count(), 1)
        self.assertContains(hirer_client.get(review), "Amina")
        self.assertNotContains(hirer_client.get(review), "Delete listing")
        self.assertRedirects(hirer_client.post(remove), review)
        self.job.refresh_from_db()
        self.assertIsNone(self.job.closed_at)
        self.assertContains(self.client.get(apply_url), 'enctype="multipart/form-data"')

        bad_resume = SimpleUploadedFile("fake.pdf", b"<html>", content_type="application/pdf")
        self.assertContains(self.client.post(apply_url, {"resume": bad_resume}), "Upload a PDF file.")
        self.assertFalse(JobApplication.objects.exists())
        content = b"%PDF-1.7\n% example fixture"
        resume = SimpleUploadedFile("resume.pdf", content, content_type="application/pdf")
        submitted = self.client.post(apply_url, {"resume": resume, "note": "I can do this on Monday."})
        application = JobApplication.objects.get(job=self.job, freelancer=self.freelancer)
        status = reverse("application_status", args=[application.pk])
        candidate = reverse("candidate_detail", args=[application.pk])
        download = reverse("download_resume", args=[application.pk])
        respond = reverse("respond_to_invitation", args=[application.pk])
        self.assertRedirects(submitted, status)
        self.assertRedirects(self.client.get(apply_url), status)
        self.assertContains(hirer_client.get(review), candidate)
        self.assertContains(hirer_client.get(candidate), "Cabinetmaking")
        self.assertContains(hirer_client.get(candidate), "mailto:amina@example.com")
        attachment = hirer_client.get(download)
        self.assertEqual(attachment.content, content)
        self.assertEqual(attachment.headers["Content-Disposition"], 'attachment; filename="resume.pdf"')
        self.assertEqual(self.client.get(download).content, content)

        interview_at = timezone.localtime(timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        self.assertRedirects(hirer_client.post(candidate, {
            "invitation_note": "Let’s proceed.",
            "interview_at": interview_at,
            "interview_details": "Meet at the workshop.",
        }), candidate)
        self.assertContains(self.client.get(reverse("dashboard")), "1 to reply")
        self.assertContains(self.client.get(status), "The hirer wishes to proceed")
        self.assertContains(self.client.get(status), "Meet at the workshop.")
        self.assertContains(self.client.get(status), "EAT")
        self.assertNotContains(hirer_client.get(review), "Delete listing")
        self.assertRedirects(self.client.post(respond, {"reply": "accept"}), status)
        self.assertContains(hirer_client.get(review), "Delete listing")
        self.assertRedirects(hirer_client.post(remove), reverse("dashboard"))
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(apply_url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("dashboard")), detail)
        self.assertContains(self.client.get(status), "Accepted")
        self.assertContains(hirer_client.get(review), "Closed")

    def test_private_hiring_pages_and_single_active_invitation(self):
        application = JobApplication.objects.create(
            job=self.job, freelancer=self.freelancer, resume_pdf=b"%PDF-",
        )
        other = User.objects.create_user(username="unrelated", role=User.Role.FREELANCER)
        second = JobApplication.objects.create(job=self.job, freelancer=other, resume_pdf=b"%PDF-")
        candidate = reverse("candidate_detail", args=[application.pk])
        respond = reverse("respond_to_invitation", args=[application.pk])
        download = reverse("download_resume", args=[application.pk])

        self.client.force_login(self.other_hirer)
        self.assertEqual(self.client.get(candidate).status_code, 404)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.assertEqual(self.client.get(reverse("job_review", args=[self.job.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("delete_listing", args=[self.job.pk])).status_code, 404)
        self.client.force_login(other)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.assertEqual(self.client.post(respond, {"reply": "accept"}).status_code, 404)

        self.client.force_login(self.hirer)
        self.assertRedirects(self.client.post(candidate), candidate)
        second_candidate = reverse("candidate_detail", args=[second.pk])
        self.assertRedirects(self.client.post(second_candidate), second_candidate)
        second.refresh_from_db()
        self.assertEqual(second.status, JobApplication.Status.SUBMITTED)
        self.client.force_login(self.freelancer)
        self.assertEqual(self.client.get(respond).status_code, 405)
        self.client.post(respond, {"reply": "decline"})
        self.client.force_login(self.hirer)
        self.assertRedirects(self.client.post(second_candidate), second_candidate)
        second.refresh_from_db()
        self.assertEqual(second.status, JobApplication.Status.INVITED)
