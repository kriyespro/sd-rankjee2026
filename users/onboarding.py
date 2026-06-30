"""Central onboarding routing — single source for role/profile gate logic."""

from .models import CustomUser

SESSION_NEEDS_ROLE_PICKER = "needs_role_picker"
SESSION_PENDING_SIGNUP_ROLE = "pending_signup_role"

PUBLIC_SELF_ASSIGNABLE_ROLES = {
    CustomUser.Role.STUDENT,
    CustomUser.Role.PARENT,
    CustomUser.Role.TUTOR,
}
SIGNUP_ROLE_QUERY_VALUES = {r.value for r in PUBLIC_SELF_ASSIGNABLE_ROLES}

# Shared copy for signup + Google onboarding role screens
ROLE_PICKER_ROWS = (
    (
        CustomUser.Role.STUDENT,
        "📚",
        "Student",
        "Practice tests, videos & track your progress",
        "Best for JEE, NEET, boards prep",
    ),
    (
        CustomUser.Role.PARENT,
        "👨‍👩‍👧",
        "Parent",
        "Find trusted tutors for your child",
        "Browse tutors & book free demos",
    ),
    (
        CustomUser.Role.TUTOR,
        "🎓",
        "Tutor",
        "List yourself & get demo requests",
        "Create a listing & get student leads",
    ),
)


def signup_role_from_request(request):
    role = (request.GET.get("role") or "").strip().upper()
    if role in SIGNUP_ROLE_QUERY_VALUES:
        return role
    return CustomUser.Role.STUDENT


def user_needs_role_picker(request):
    return bool(request.session.get(SESSION_NEEDS_ROLE_PICKER))


def incomplete_onboarding_url_name(request):
    """Where to send users who have not finished onboarding."""
    if user_needs_role_picker(request):
        return "users:onboarding_role"
    if request.user.role in PUBLIC_SELF_ASSIGNABLE_ROLES:
        return "users:onboarding_profile"
    return "users:onboarding_role"


def post_auth_redirect_target(request, fallback="learning:index", *, from_email_signup=False):
    if request.user.is_authenticated and not getattr(request.user, "onboarding_completed", True):
        if from_email_signup:
            return "users:onboarding_profile"
        return incomplete_onboarding_url_name(request)
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return fallback


def clear_onboarding_session_flags(request):
    request.session.pop(SESSION_NEEDS_ROLE_PICKER, None)
    request.session.pop(SESSION_PENDING_SIGNUP_ROLE, None)


def begin_email_signup_onboarding(request, user):
    """Email signup already picked a role on the signup form."""
    if user.role not in PUBLIC_SELF_ASSIGNABLE_ROLES:
        user.role = CustomUser.Role.STUDENT
    user.onboarding_completed = False
    user.save(update_fields=["role", "onboarding_completed"])
    clear_onboarding_session_flags(request)


def store_pending_google_signup_role(request):
    """Persist role chosen on signup page before OAuth redirect."""
    role = signup_role_from_request(request)
    if role in SIGNUP_ROLE_QUERY_VALUES:
        request.session[SESSION_PENDING_SIGNUP_ROLE] = role
    else:
        request.session.pop(SESSION_PENDING_SIGNUP_ROLE, None)


def apply_social_signup_onboarding(request, user):
    """Google/OAuth signups: use pre-selected role or show role picker once."""
    pending_role = None
    if request and hasattr(request, "session"):
        pending_role = request.session.pop(SESSION_PENDING_SIGNUP_ROLE, None)

    if getattr(user, "onboarding_completed", True):
        user.onboarding_completed = False

    update_fields = ["onboarding_completed"]
    if pending_role in SIGNUP_ROLE_QUERY_VALUES:
        user.role = pending_role
        update_fields.append("role")
        if request and hasattr(request, "session"):
            request.session.pop(SESSION_NEEDS_ROLE_PICKER, None)
    elif request and hasattr(request, "session"):
        request.session[SESSION_NEEDS_ROLE_PICKER] = True

    user.save(update_fields=update_fields)


def complete_role_selection(request, user, role):
    user.role = role
    user.save(update_fields=["role"])
    request.session.pop(SESSION_NEEDS_ROLE_PICKER, None)
