from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from .forms import CandidateInvitationForm, JobApplicationForm
from .models import Job, JobApplication, JobView, User


def can_view_jobs(user):
    return user.role in User.Role.values and (
        user.has_perm("marketplace.view_job") or user.has_perm("marketplace.change_job")
    )


def owned_jobs(user):
    if user.role != User.Role.HIRER:
        raise PermissionDenied
    return Job.objects.filter(hirer=user)


def applicant_applications(user):
    if user.role != User.Role.FREELANCER:
        raise PermissionDenied
    return JobApplication.objects.filter(freelancer=user)


@never_cache
@login_required
@require_safe
def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related("hirer"), pk=pk)
    is_owner = request.user.role == User.Role.HIRER and job.hirer_id == request.user.pk
    if not is_owner:
        if job.closed_at:
            raise Http404
        if not can_view_jobs(request.user):
            raise PermissionDenied
        if request.method == "GET":
            JobView.objects.get_or_create(job=job, viewer=request.user)

    can_apply = request.user.role == User.Role.FREELANCER and not job.closed_at
    application = None
    if can_apply:
        application = job.applications.filter(freelancer=request.user).only("id").first()
    return render(request, "marketplace/job_detail.html", {
        "job": job, "application": application, "is_owner": is_owner, "can_apply": can_apply,
    })


@never_cache
@login_required
def apply_for_job(request, pk):
    if request.user.role != User.Role.FREELANCER or not can_view_jobs(request.user):
        raise PermissionDenied
    job = get_object_or_404(Job.objects.select_related("hirer"), pk=pk, closed_at__isnull=True)
    previous = job.applications.filter(freelancer=request.user).only("id").first()
    if previous:
        return redirect("application_status", pk=previous.pk)

    form = JobApplicationForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        resume_pdf = form.cleaned_data["resume"].read()
        with transaction.atomic():
            # Serialize posting an application with closing this listing, including on SQLite.
            if not Job.objects.filter(pk=pk, closed_at__isnull=True).update(closed_at=None):
                raise Http404
            application, created = JobApplication.objects.defer("resume_pdf").get_or_create(
                job=job, freelancer=request.user,
                defaults={"note": form.cleaned_data["note"], "resume_pdf": resume_pdf},
            )
        if created:
            messages.success(request, "Your application was sent.")
        return redirect("application_status", pk=application.pk)
    return render(request, "marketplace/apply.html", {"form": form, "job": job})


@never_cache
@login_required
@require_safe
def job_review(request, pk):
    job = get_object_or_404(owned_jobs(request.user), pk=pk)
    applicants = list(job.applications.select_related("freelancer").defer("resume_pdf"))
    accepted = next((item for item in applicants if item.status == JobApplication.Status.ACCEPTED), None)
    return render(request, "marketplace/job_review.html", {
        "job": job, "applicants": applicants, "accepted": accepted,
        "viewers": job.views.select_related("viewer"),
    })


@never_cache
@login_required
def candidate_detail(request, pk):
    application = get_object_or_404(
        JobApplication.objects.filter(job__in=owned_jobs(request.user))
        .select_related("job", "freelancer", "freelancer__freelancer_profile").defer("resume_pdf"),
        pk=pk,
    )
    active_statuses = [JobApplication.Status.INVITED, JobApplication.Status.ACCEPTED]
    can_invite = (
        not application.job.closed_at
        and application.status == JobApplication.Status.SUBMITTED
        and not application.job.applications.filter(status__in=active_statuses).exists()
    )
    form = CandidateInvitationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if not can_invite:
            messages.error(request, "This listing already has an active candidate or is closed.")
            return redirect("candidate_detail", pk=pk)
        if form.is_valid():
            try:
                with transaction.atomic():
                    invited = JobApplication.objects.filter(
                        pk=pk, status=JobApplication.Status.SUBMITTED, job__closed_at__isnull=True,
                    ).update(status=JobApplication.Status.INVITED, **form.cleaned_data)
            except IntegrityError:
                if not application.job.applications.filter(status__in=active_statuses).exists():
                    raise
                invited = False
            if invited:
                messages.success(request, "Candidate approved and notified.")
            else:
                messages.error(request, "An invitation is already active for this listing.")
            return redirect("candidate_detail", pk=pk)

    return render(request, "marketplace/candidate.html", {
        "application": application, "candidate": application.freelancer, "form": form,
        "can_invite": can_invite,
    })


@never_cache
@login_required
@require_safe
def application_status(request, pk):
    application = get_object_or_404(
        applicant_applications(request.user).select_related("job__hirer").defer("resume_pdf"), pk=pk,
    )
    return render(request, "marketplace/application_status.html", {"application": application})


@never_cache
@login_required
@require_POST
def respond_to_invitation(request, pk):
    applications = applicant_applications(request.user)
    application = get_object_or_404(applications.only("id"), pk=pk)
    replies = {"accept": JobApplication.Status.ACCEPTED, "decline": JobApplication.Status.DECLINED}
    reply = replies.get(request.POST.get("reply"))
    if not reply:
        return redirect("application_status", pk=pk)
    updated = applications.filter(
        pk=application.pk, status=JobApplication.Status.INVITED, job__closed_at__isnull=True,
    ).update(status=reply)
    if updated:
        messages.success(request, f"Invitation {reply.label.lower()}. The hirer can see your response.")
    else:
        messages.error(request, "This invitation is no longer awaiting a response.")
    return redirect("application_status", pk=pk)


@never_cache
@login_required
@require_safe
def download_resume(request, pk):
    user = request.user
    if user.role == User.Role.HIRER:
        access = Q(job__hirer=user)
    elif user.role == User.Role.FREELANCER:
        access = Q(freelancer=user)
    else:
        raise PermissionDenied
    application = get_object_or_404(JobApplication.objects.only("resume_pdf"), access, pk=pk)
    return HttpResponse(bytes(application.resume_pdf), content_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="resume.pdf"',
        "X-Content-Type-Options": "nosniff",
    })


@never_cache
@login_required
@require_POST
def delete_listing(request, pk):
    jobs = owned_jobs(request.user)
    job = get_object_or_404(jobs.only("id", "closed_at"), pk=pk)
    if job.closed_at:
        return redirect("job_review", pk=pk)
    closed = jobs.filter(
        pk=pk, closed_at__isnull=True, applications__status=JobApplication.Status.ACCEPTED,
    ).update(closed_at=timezone.now())
    if closed:
        messages.success(request, "Listing deleted from the job board. Its hiring history is still available.")
        return redirect("dashboard")
    messages.error(request, "A candidate needs to accept before you can delete this listing.")
    return redirect("job_review", pk=pk)
