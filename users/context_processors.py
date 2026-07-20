"""Minimal EN/HI labels for nav (FEATURE-13 lean)."""


def _course_cart_count(request):
    if not request.user.is_authenticated:
        return 0
    raw = request.session.get("course_cart_ids") or []
    seen = set()
    n = 0
    for x in raw:
        try:
            pk = int(x)
        except (TypeError, ValueError):
            continue
        if pk > 0 and pk not in seen:
            seen.add(pk)
            n += 1
    return n


def ui_labels(request):
    lang = request.session.get('ui_lang', 'en')
    if lang == 'hi':
        labels = {
            'assess': 'टेस्ट',
            'test': 'टेस्ट',
            'academy': 'अकादमी',
            'rewards': 'कमाई',
            'dashboard': 'डैशबोर्ड',
            'login': 'लॉग इन',
            'join': 'जॉइन करें',
            'logout': 'लॉग आउट',
            'home': 'होम',
            'learn': 'सीखें',
            'earn': 'कमाएँ',
            'pro': '⭐ प्रो',
            'get_started': 'शुरू करें',
            'watch_earn': 'देखो और कमाओ',
            'enter_jackpot': 'जैकपॉट में जाएँ',
        }
    else:
        labels = {
            'assess': 'Assess',
            'test': 'Test',
            'academy': 'Academy',
            'rewards': 'Rewards',
            'dashboard': 'Dashboard',
            'login': 'Login',
            'join': 'Join',
            'logout': 'Logout',
            'home': 'Home',
            'learn': 'Learn',
            'earn': 'Earn',
            'pro': '⭐ Go Pro',
            'get_started': 'Get started free',
            'watch_earn': 'Watch & earn ₹',
            'enter_jackpot': 'Enter jackpot',
        }
    return {"uil": labels, "ui_lang": lang, "course_cart_count": _course_cart_count(request), "exam_paywall_enabled": _exam_paywall_enabled()}


def _exam_paywall_enabled() -> bool:
    from django.conf import settings

    return bool(getattr(settings, "EXAM_PAYWALL_ENABLED", True))
