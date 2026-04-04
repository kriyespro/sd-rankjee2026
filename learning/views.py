from django.db.models import Q
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from assessment.models import UserAttempt, Skill
from .models import ConceptVideo

@login_required
def learning_index(request):
    skill_id = request.GET.get('skill')
    concept = (request.GET.get('concept') or '').strip()
    
    if skill_id:
        # Prefer skill-linked videos, but fall back to concept_tag videos for weak areas
        videos = ConceptVideo.objects.filter(skill_id=skill_id)
        current_skill = Skill.objects.filter(id=skill_id).first()
        if concept and not videos.exists():
            videos = ConceptVideo.objects.filter(concept_tag__iexact=concept)
        elif concept:
            videos = videos.filter(Q(concept_tag__iexact=concept) | Q(concept_tag__icontains=concept))
    else:
        # Get the user's most recent failed attempt and map to available videos
        latest_attempt = UserAttempt.objects.filter(
            user=request.user, passed=False
        ).order_by('-attempt_date').first()
        current_skill = latest_attempt.skill if latest_attempt else None

        if concept:
            videos = ConceptVideo.objects.filter(concept_tag__iexact=concept)
        elif latest_attempt and latest_attempt.weak_concepts:
            # Use case-insensitive matching to avoid tag casing mismatches
            q = Q()
            for tag in latest_attempt.weak_concepts:
                if tag:
                    q |= Q(concept_tag__iexact=str(tag).strip())
            videos = ConceptVideo.objects.filter(q) if q else ConceptVideo.objects.none()
        else:
            videos = ConceptVideo.objects.all()[:6]

    return render(request, 'learning/index.jinja', {
        'videos': videos,
        'current_skill': current_skill,
    })

