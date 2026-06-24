from django.db.models import Count, Q
from django.shortcuts import render
from assessment.models import UserAttempt, Skill
from .models import ConceptVideo


def learning_index(request):
    skill_id = request.GET.get('skill')
    concept = (request.GET.get('concept') or '').strip()

    all_videos = ConceptVideo.objects.select_related("skill")
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
        latest_attempt = UserAttempt.objects.filter(user=request.user).select_related("skill").order_by("-attempt_date").first()
        latest_failed_attempt = UserAttempt.objects.filter(user=request.user, passed=False).select_related("skill").order_by("-attempt_date").first()

    if not selected_skill:
        selected_skill = (latest_attempt.skill if latest_attempt else None) or (category_skills[0] if category_skills else None)

    if selected_skill:
        videos = all_videos.filter(skill=selected_skill)
    else:
        videos = all_videos

    if concept:
        filtered = videos.filter(Q(concept_tag__iexact=concept) | Q(concept_tag__icontains=concept))
        if filtered.exists():
            videos = filtered
        else:
            global_concept = all_videos.filter(Q(concept_tag__iexact=concept) | Q(concept_tag__icontains=concept))
            if global_concept.exists():
                videos = global_concept
    elif latest_failed_attempt and latest_failed_attempt.weak_concepts:
        q = Q()
        for tag in latest_failed_attempt.weak_concepts:
            if tag:
                q |= Q(concept_tag__iexact=str(tag).strip())
        if q:
            weak_filtered = videos.filter(q)
            if weak_filtered.exists():
                videos = weak_filtered

    # Final safety net: never return blank just because weak-concept mapping failed.
    if not videos.exists():
        if selected_skill and all_videos.filter(skill=selected_skill).exists():
            videos = all_videos.filter(skill=selected_skill)
        else:
            videos = all_videos.order_by("-id")

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

