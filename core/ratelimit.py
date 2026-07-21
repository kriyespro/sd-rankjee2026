"""Lightweight cache-based rate limiting for public lead/request forms.

Uses the Redis cache already configured in settings (`django.core.cache`) —
no new dependency (e.g. django-ratelimit) needed for this. Fixed-window
counter per identity (user id when authenticated, else IP).
"""
from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect


def ratelimit(rate: int, period: int, key_prefix: str):
    """
    Allow at most `rate` calls per `period` seconds per user/IP.
    On limit hit: show an error message and redirect back instead of
    processing the view (safe for POST-then-redirect form handlers).
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return view_func(request, *args, **kwargs)

            if request.user.is_authenticated:
                ident = f"u{request.user.pk}"
            else:
                ident = request.META.get("REMOTE_ADDR", "anon")
            cache_key = f"ratelimit:{key_prefix}:{ident}"

            if cache.add(cache_key, 1, timeout=period):
                count = 1
            else:
                try:
                    count = cache.incr(cache_key)
                except ValueError:
                    cache.set(cache_key, 1, timeout=period)
                    count = 1

            if count > rate:
                messages.error(request, "Too many requests. Please wait a bit and try again.")
                return redirect(request.META.get("HTTP_REFERER") or "/")

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
