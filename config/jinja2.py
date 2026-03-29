from django.templatetags.static import static
from django.urls import reverse as django_reverse
from jinja2 import Environment


def url(viewname, *args, **kwargs):
    """Wrapper around Django's reverse() that correctly handles positional URL args."""
    if args:
        return django_reverse(viewname, args=args)
    if kwargs:
        return django_reverse(viewname, kwargs=kwargs)
    return django_reverse(viewname)


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': static,
        'url': url,
    })
    return env
