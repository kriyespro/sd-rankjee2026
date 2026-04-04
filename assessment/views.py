import random

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from users.models import CustomUser
from .models import (
    SkillPath,
    Skill,
    Question,
    UserAttempt,
    QuestionSet,
    UserSetAttempt,
    DailyJackpot,
    JackpotWinner,
    SkillTestEntitlement,
)
from users.gamification import on_test_submitted

@login_required
def test_index(request):
    paths = SkillPath.objects.filter(is_active=True).prefetch_related('skills')
    unassigned_skills = Skill.objects.filter(is_active=True, path__isnull=True)
    attempts = UserAttempt.objects.filter(user=request.user).values_list('skill_id', flat=True)
    return render(request, 'assessment/test_list.jinja', {
        'paths': paths,
        'unassigned_skills': unassigned_skills,
        'attempted_ids': list(attempts),
    })

@login_required
def jackpot_lobby(request):
    now = timezone.now()
    # Find the nearest active jackpot (current or future)
    jackpot = DailyJackpot.objects.filter(is_active=True, is_completed=False).order_by('scheduled_time').first()
    
    if not jackpot:
        return render(request, 'assessment/jackpot_lobby.jinja', {'no_jackpot': True})

    # AUTO-SETTLE: If jackpot was scheduled more than 1 hour ago and not completed, settle it
    if now > (jackpot.scheduled_time + timezone.timedelta(hours=1)) and not jackpot.is_completed:
        settle_jackpot(jackpot)
        return redirect('assessment:jackpot_lobby')

    is_live = now >= jackpot.scheduled_time
    time_to_go = (jackpot.scheduled_time - now).total_seconds() if not is_live else 0
    
    # Check if user already participated
    already_played = JackpotWinner.objects.filter(jackpot=jackpot, user=request.user).exists()
    
    # Get previous winners for social proof
    last_jackpot = DailyJackpot.objects.filter(is_completed=True).order_by('-scheduled_time').first()
    recent_winners = last_jackpot.winners.all()[:10] if last_jackpot else []

    return render(request, 'assessment/jackpot_lobby.jinja', {
        'jackpot': jackpot,
        'is_live': is_live,
        'time_to_go': int(time_to_go),
        'already_played': already_played,
        'recent_winners': recent_winners,
    })

def settle_jackpot(jackpot):
    """
    Ranks top 10 participants for a jackpot based on Score (primary) and Time (secondary).
    Awards money from the prize pool.
    """
    with transaction.atomic():
        attempts = UserAttempt.objects.filter(
            skill=jackpot.skill,
            attempt_date__gte=jackpot.scheduled_time,
            attempt_date__lte=jackpot.scheduled_time + timezone.timedelta(hours=1)
        ).order_by('-score', 'attempt_date')

        prizes = [150, 100, 75, 50, 25, 20, 20, 20, 20, 20]
        winners_count = 0
        seen_users = set()
        
        for attempt in attempts:
            if attempt.user.id in seen_users: continue
            if winners_count >= 10: break
            
            seen_users.add(attempt.user.id)
            prize = prizes[winners_count]
            
            JackpotWinner.objects.create(
                jackpot=jackpot,
                user=attempt.user,
                rank=winners_count + 1,
                score=attempt.score,
                time_taken_seconds=300,
                award_amount=prize
            )
            
            attempt.user.add_wallet(
                prize,
                transaction_type='EARN_JACKPOT',
                reference_id=str(jackpot.id),
            )
            winners_count += 1
            
        jackpot.is_completed = True
        jackpot.save(update_fields=['is_completed'])

@login_required
def take_test(request, skill_id):
    skill = get_object_or_404(Skill, pk=skill_id, is_active=True)
    
    # NEW: Determine which set the user is on
    user_passed_sets = UserSetAttempt.objects.filter(
        user=request.user, 
        question_set__skill=skill,
        passed=True
    ).values_list('question_set_id', flat=True)
    
    current_set = skill.sets.filter(is_active=True).exclude(id__in=user_passed_sets).order_by('order').first()
    
    # SELF-HEALING: If there are unassigned questions or no sets exist, auto-partition
    if skill.questions.filter(question_set__isnull=True).exists() or not skill.sets.exists():
        if skill.questions.exists():
            skill.partition_questions()
            # Refresh current_set after partitioning logic
            current_set = skill.sets.filter(is_active=True).exclude(id__in=user_passed_sets).order_by('order').first()
    
    # If sets exist but all are passed, then they have mastered it
    if skill.sets.exists() and not current_set:
        from django.contrib import messages
        messages.success(request, f"Congratulations! You've mastered all levels of {skill.name}.")
        return redirect('dashboard:index')

    # Monetization: trials or wallet; entitlement row prevents double charge (tabs / races)
    session_key = f'active_test_paid_{skill.id}'
    if not request.session.get(session_key):
        if SkillTestEntitlement.objects.filter(user_id=request.user.id, skill_id=skill.id).exists():
            request.session[session_key] = True
        else:
            with transaction.atomic():
                u = CustomUser.objects.select_for_update().get(pk=request.user.pk)
                if SkillTestEntitlement.objects.filter(user_id=u.id, skill_id=skill.id).exists():
                    request.session[session_key] = True
                elif u.is_superuser or u.is_staff:
                    SkillTestEntitlement.objects.create(user=u, skill=skill)
                    request.session[session_key] = True
                elif getattr(u, "is_premium", False):
                    SkillTestEntitlement.objects.create(user=u, skill=skill)
                    request.session[session_key] = True
                elif u.trial_tests_left > 0 and getattr(u, "trial_tests_used", 0) < 3:
                    u.trial_tests_left -= 1
                    u.trial_tests_used = (u.trial_tests_used or 0) + 1
                    u.save(update_fields=['trial_tests_left', 'trial_tests_used'])
                    SkillTestEntitlement.objects.create(user=u, skill=skill)
                    request.session[session_key] = True
                elif u.wallet_balance >= 10:
                    u.add_wallet(-10, transaction_type='DEDUCT_TEST', reference_id=str(skill.id))
                    SkillTestEntitlement.objects.create(user=u, skill=skill)
                    request.session[session_key] = True
                else:
                    from django.contrib import messages

                    messages.error(
                        request,
                        "Insufficient Wallet Balance! Tests cost ₹10 after your free trials. Earn money on the Freelance Board or invite friends!",
                    )
                    return redirect('core:earnings')
    
    if current_set:
        questions = list(current_set.questions.all())
    else:
        # LEGACY FALLBACK: If no sets defined yet, pick 10 random ones
        all_questions = Question.objects.filter(skill=skill)
        easy_qs = list(all_questions.filter(difficulty='EASY').order_by('?')[:4])
        med_qs = list(all_questions.filter(difficulty='MEDIUM').order_by('?')[:4])
        hard_qs = list(all_questions.filter(difficulty='HARD').order_by('?')[:2])
        questions = easy_qs + med_qs + hard_qs
        if len(questions) < 10:
            exclude_ids = [q.id for q in questions]
            remaining = list(all_questions.exclude(id__in=exclude_ids).order_by('?')[:10 - len(questions)])
            questions.extend(remaining)
        random.shuffle(questions)

    if not questions:
        from django.contrib import messages
        messages.info(request, "This topic doesn't have enough questions for a test yet.")
        return redirect('dashboard:index')
    
    # Store the question IDs in session so we know which ones were in THIS test
    request.session[f'test_questions_{skill.id}'] = [q.id for q in questions]
    request.session[f'test_set_id_{skill.id}'] = current_set.id if current_set else None

    if not questions:
        return redirect('assessment:index')
    return render(request, 'assessment/take_test.jinja', {
        'skill': skill,
        'current_set': current_set,
        'questions': questions,
    })


@login_required
def submit_test(request, skill_id):
    if request.method != 'POST':
        return redirect('assessment:index')
    skill = get_object_or_404(Skill, pk=skill_id)
    set_id = request.POST.get('set_id') or request.session.get(f'test_set_id_{skill.id}')
    current_set = QuestionSet.objects.filter(id=set_id).first() if set_id else None

    session_key = f'active_test_paid_{skill.id}'
    if session_key in request.session:
        del request.session[session_key]
    SkillTestEntitlement.objects.filter(user=request.user, skill=skill).delete()

    # Get only the questions that were actually in the test
    question_ids = request.session.get(f'test_questions_{skill.id}', [])
    if not question_ids:
        questions = Question.objects.filter(skill=skill)
    else:
        questions = Question.objects.filter(id__in=question_ids)
        del request.session[f'test_questions_{skill.id}']
    
    # Cleanup session set tracking
    if f'test_set_id_{skill.id}' in request.session: 
        del request.session[f'test_set_id_{skill.id}']

    time_taken_seconds = 0
    try:
        time_taken_seconds = int(request.POST.get('time_taken_seconds', 0))
    except (ValueError, TypeError):
        pass

    total = questions.count()
    correct = 0
    weak_concepts = []
    submitted_answers = []
    
    for q in questions:
        answer = request.POST.get(f'q_{q.id}')
        is_correct = False
        if answer and answer.upper() == q.correct_option:
            correct += 1
            is_correct = True
        else:
            if q.concept_tag not in weak_concepts:
                weak_concepts.append(q.concept_tag)
                
        submitted_answers.append({
            'question': q,
            'user_answer': answer,
            'is_correct': is_correct
        })
        
    score = int((correct / total) * 100) if total > 0 else 0
    passed = score >= 80

    # Record both skill attempt and set attempt
    UserAttempt.objects.create(
        user=request.user,
        skill=skill,
        score=score,
        time_taken_seconds=time_taken_seconds,
        passed=passed,
        weak_concepts=weak_concepts,
    )
    if current_set:
        UserSetAttempt.objects.create(
            user=request.user,
            question_set=current_set,
            score=score,
            time_taken_seconds=time_taken_seconds,
            passed=passed,
        )

    # Gamification: award XP + badges
    on_test_submitted(request.user, passed, skill=skill)

    # Logic for next step
    next_set = None
    next_skill = None
    if passed:
        if current_set:
            next_set = skill.sets.filter(order__gt=current_set.order, is_active=True).first()
        
        if not next_set:
            next_skill = skill.get_next_skill()
            
            # Certificate Issuance: If they passed the LAST set, they master a skill
            from .models import Certificate
            cert, created = Certificate.objects.get_or_create(user=request.user, skill=skill)
            if created:
                # Send notification
                from users.models import Notification
                Notification.objects.create(
                    user=request.user,
                    message=f"🏆 Certificate Earned! You've mastered {skill.name}.",
                    link=f"/assessment/certificate/{cert.certificate_id}/view/"
                )

    return render(request, 'assessment/result.jinja', {
        'skill': skill,
        'current_set': current_set,
        'next_set': next_set,
        'next_skill': next_skill,
        'score': score,
        'passed': passed,
        'weak_concepts': weak_concepts,
        'correct': correct,
        'total': total,
        'submitted_answers': submitted_answers,
        'time_taken_seconds': time_taken_seconds,
    })

from django.http import FileResponse
from .utils import generate_certificate_pdf
from .models import Certificate

@login_required
def view_certificate(request, certificate_id):
    cert = get_object_or_404(Certificate, certificate_id=certificate_id, user=request.user)
    return render(request, 'assessment/certificate_view.jinja', {'cert': cert})

@login_required
def download_certificate(request, certificate_id):
    cert = get_object_or_404(Certificate, certificate_id=certificate_id, user=request.user)
    
    # Premium Gate: Check if user is premium to download PDF
    if not request.user.is_premium:
        from django.contrib import messages
        messages.warning(request, "Premium Subscription required to download PDF certificates. Upgrade now!")
        return redirect('payments:plans')

    buffer = generate_certificate_pdf(request.user, cert.skill, cert.certificate_id)
    return FileResponse(buffer, as_attachment=True, filename=f"Certificate_{cert.skill.name.replace(' ', '_')}.pdf")
