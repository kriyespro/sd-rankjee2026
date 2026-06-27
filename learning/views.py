from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from assessment.models import UserAttempt, Skill
from .models import ConceptVideo


def _pick_videos(all_videos, selected_skill, concept, latest_failed_attempt):
    """Filter videos in Python after one queryset fetch — avoids repeated .exists() queries."""
    if selected_skill:
        pool = [v for v in all_videos if v.skill_id == selected_skill.id]
    else:
        pool = list(all_videos)

    if concept:
        concept_l = concept.lower()
        filtered = [
            v
            for v in pool
            if v.concept_tag
            and (
                v.concept_tag.lower() == concept_l
                or concept_l in v.concept_tag.lower()
            )
        ]
        if filtered:
            return filtered
        return [
            v
            for v in all_videos
            if v.concept_tag
            and (
                v.concept_tag.lower() == concept_l
                or concept_l in v.concept_tag.lower()
            )
        ]

    if latest_failed_attempt and latest_failed_attempt.weak_concepts:
        tags = {str(tag).strip().lower() for tag in latest_failed_attempt.weak_concepts if tag}
        if tags:
            weak_filtered = [
                v
                for v in pool
                if v.concept_tag and v.concept_tag.strip().lower() in tags
            ]
            if weak_filtered:
                return weak_filtered

    if pool:
        return pool
    if selected_skill:
        skill_pool = [v for v in all_videos if v.skill_id == selected_skill.id]
        if skill_pool:
            return skill_pool
    return sorted(all_videos, key=lambda v: v.id, reverse=True)


@login_required
@transaction.non_atomic_requests
def learning_index(request):
    skill_id = request.GET.get('skill')
    concept = (request.GET.get('concept') or '').strip()

    all_videos = list(ConceptVideo.objects.select_related("skill").order_by("-id"))
    category_skills = list(
        Skill.objects.filter(videos__isnull=False, is_active=True)
        .annotate(video_count=Count("videos"))
        .order_by("order", "name")
        .distinct()
    )

    selected_skill = None
    if skill_id:
        selected_skill = Skill.objects.filter(id=skill_id, is_active=True).first()

    latest_attempt = None
    latest_failed_attempt = None
    if request.user.is_authenticated:
        latest_attempt = (
            UserAttempt.objects.filter(user=request.user)
            .select_related("skill")
            .order_by("-attempt_date")
            .first()
        )
        latest_failed_attempt = (
            UserAttempt.objects.filter(user=request.user, passed=False)
            .select_related("skill")
            .order_by("-attempt_date")
            .first()
        )

    if not selected_skill:
        selected_skill = (latest_attempt.skill if latest_attempt else None) or (
            category_skills[0] if category_skills else None
        )

    videos = _pick_videos(all_videos, selected_skill, concept, latest_failed_attempt)

    return render(
        request,
        "learning/index.jinja",
        {
            "videos": videos[:24],
            "current_skill": selected_skill,
            "category_skills": category_skills,
            "selected_concept": concept,
        },
    )
