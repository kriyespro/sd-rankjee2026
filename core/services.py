from .models import Course, CourseDemoRequest


def request_course_preview(user, course: Course):
    """RECORDED course flow — instant free preview, no approval step.

    Returns the LmsAssignment carrying the marked preview video, or None if
    no faculty has marked one yet.
    """
    from lms.models import LmsAssignment

    assignment = (
        LmsAssignment.objects.filter(
            course__catalog_course=course,
            is_free_preview=True,
            is_published=True,
            concept_video__isnull=False,
        )
        .select_related("concept_video")
        .first()
    )
    CourseDemoRequest.objects.get_or_create(
        course=course,
        requester=user,
        request_type=CourseDemoRequest.RequestType.PREVIEW,
        defaults={"status": CourseDemoRequest.Status.COMPLETED},
    )
    return assignment


def request_course_live_demo(user, course: Course, message: str = "", contact_phone: str = ""):
    """HYBRID course flow — routes to the catalog course's default LMS batch owner."""
    from lms.models import LmsCourse

    lms_course = (
        LmsCourse.objects.filter(catalog_course=course, is_active=True)
        .order_by("-is_default_for_catalog")
        .first()
    )
    faculty = lms_course.owner if lms_course else None

    return CourseDemoRequest.objects.create(
        course=course,
        requester=user,
        request_type=CourseDemoRequest.RequestType.LIVE_DEMO,
        assigned_faculty=faculty,
        message=message,
        contact_phone=contact_phone,
    )


def faculty_pending_course_demo_requests(user):
    return CourseDemoRequest.objects.filter(
        assigned_faculty=user,
        request_type=CourseDemoRequest.RequestType.LIVE_DEMO,
        status=CourseDemoRequest.Status.PENDING,
    ).select_related("course")
