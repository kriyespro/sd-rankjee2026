from django.urls import reverse
from django.utils import timezone

from core.sitemap_utils import CanonicalHostSitemap

from .models import BlogPost


class BlogPostSitemap(CanonicalHostSitemap):
    changefreq = 'weekly'
    priority = 0.75

    def items(self):
        return BlogPost.objects.filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        ).order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:detail', kwargs={'slug': obj.slug})
