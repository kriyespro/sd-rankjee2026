from hometutor.models import TutorEngagement, TutorProfile


def get_tutor_profile(user):
    try:
        return user.tutor_profile
    except TutorProfile.DoesNotExist:
        return None


def engaged_tutor_user_ids(student):
    """User IDs of tutors with an ACTIVE engagement for this student/parent."""
    return set(
        TutorEngagement.objects.filter(
            student=student,
            status=TutorEngagement.Status.ACTIVE,
            tutor_profile__user__isnull=False,
        ).values_list('tutor_profile__user_id', flat=True)
    )


def student_can_access_tutor(student, tutor_user_id: int) -> bool:
    return tutor_user_id in engaged_tutor_user_ids(student)
