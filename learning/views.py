from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from assessment.models import UserAttempt, Skill
from .models import ConceptVideo

@login_required
def learning_index(request):
    skill_id = request.GET.get('skill')
    
    if skill_id:
        videos = ConceptVideo.objects.filter(skill_id=skill_id)
        current_skill = Skill.objects.filter(id=skill_id).first()
    else:
        # Get the user's most recent failed attempt and map to available videos
        latest_attempt = UserAttempt.objects.filter(
            user=request.user, passed=False
        ).order_by('-attempt_date').first()
        current_skill = latest_attempt.skill if latest_attempt else None

        if latest_attempt and latest_attempt.weak_concepts:
            videos = ConceptVideo.objects.filter(
                concept_tag__in=latest_attempt.weak_concepts
            )
        else:
            videos = ConceptVideo.objects.all()[:6]

    return render(request, 'learning/index.jinja', {
        'videos': videos,
        'current_skill': current_skill,
    })

