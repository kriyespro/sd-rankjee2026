"""Minimal EN/HI labels for nav (FEATURE-13 lean)."""


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
    return {'uil': labels, 'ui_lang': lang}
