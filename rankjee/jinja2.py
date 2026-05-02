import logging

from django.templatetags.static import static
from django.urls import NoReverseMatch
from django.urls import reverse as django_reverse
from jinja2 import Environment

logger = logging.getLogger(__name__)


def _fallback_when_namespace_missing(viewname, args, kwargs):
    """
    If URLconf was deployed without blog/ or study/ includes, reverse() raises
    NoReverseMatch('… is not a registered namespace'). Return literal paths that
    match blog/urls.py and tutor_study/urls.py so pages still render (links work
    once URLconf is fixed on the server).
    """
    args = args or ()
    kwargs = kwargs or {}
    pk = kwargs.get('pk')
    if pk is None and args:
        pk = args[0]
    slug = kwargs.get('slug')

    if viewname == 'blog:index':
        return '/blog/'
    if viewname == 'blog:detail':
        if slug:
            return f'/blog/post/{slug}/'
        return '/blog/'

    study_fixed = {
        'study:student_hub': '/study/',
        'study:tutor_dashboard': '/study/tutor/',
        'study:tutor_material_create': '/study/tutor/materials/new/',
        'study:tutor_assignment_create': '/study/tutor/assignments/new/',
    }
    if viewname in study_fixed:
        return study_fixed[viewname]
    if viewname == 'study:student_material' and pk is not None:
        return f'/study/material/{pk}/'
    if viewname == 'study:student_assignment' and pk is not None:
        return f'/study/assignment/{pk}/'
    if viewname == 'study:tutor_material_edit' and pk is not None:
        return f'/study/tutor/materials/{pk}/edit/'
    if viewname == 'study:tutor_assignment_edit' and pk is not None:
        return f'/study/tutor/assignments/{pk}/edit/'
    if viewname == 'study:tutor_assignment_submissions' and pk is not None:
        return f'/study/tutor/assignments/{pk}/submissions/'

    if isinstance(viewname, str):
        if viewname.startswith('blog:'):
            return '/blog/'
        if viewname.startswith('study:'):
            return '/study/'
    return None


def url(viewname, *args, **kwargs):
    """Wrapper around Django's reverse() that correctly handles positional URL args."""
    try:
        if args:
            return django_reverse(viewname, args=args)
        if kwargs:
            return django_reverse(viewname, kwargs=kwargs)
        return django_reverse(viewname)
    except NoReverseMatch as exc:
        if 'not a registered namespace' not in str(exc):
            raise
        fb = _fallback_when_namespace_missing(viewname, args, kwargs)
        if fb is not None:
            logger.warning(
                'URL reverse skipped missing namespace for %r; using fallback %r. '
                'Ensure rankjee/urls.py includes blog and tutor_study routes.',
                viewname,
                fb,
            )
            return fb
        raise


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': static,
        'url': url,
    })
    return env
