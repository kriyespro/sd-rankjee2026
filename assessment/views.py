from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import SkillPath, Skill, Question, UserAttempt, QuestionSet, UserSetAttempt
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


import random

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

    # Monetization: Test-Teach-Retest requires trials or wallet balance
    session_key = f'active_test_paid_{skill.id}'
    if not request.session.get(session_key):
        user = request.user
        if user.is_superuser or user.is_staff:
            request.session[session_key] = True
        elif user.trial_tests_left > 0:
            user.trial_tests_left -= 1
            user.save(update_fields=['trial_tests_left'])
            request.session[session_key] = True
        elif user.wallet_balance >= 10:
            user.wallet_balance -= 10
            user.save(update_fields=['wallet_balance'])
            request.session[session_key] = True
        else:
            from django.contrib import messages
            messages.error(request, "Insufficient Wallet Balance! Tests cost ₹10 after your free trials. Earn money on the Freelance Board or invite friends!")
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

    total = questions.count()
    correct = 0
    weak_concepts = []
    for q in questions:
        answer = request.POST.get(f'q_{q.id}')
        if answer and answer.upper() == q.correct_option:
            correct += 1
        else:
            if q.concept_tag not in weak_concepts:
                weak_concepts.append(q.concept_tag)
    score = int((correct / total) * 100) if total > 0 else 0
    passed = score >= 80

    # Record both skill attempt and set attempt
    UserAttempt.objects.create(
        user=request.user,
        skill=skill,
        score=score,
        passed=passed,
        weak_concepts=weak_concepts,
    )
    if current_set:
        UserSetAttempt.objects.create(
            user=request.user,
            question_set=current_set,
            score=score,
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
    })
