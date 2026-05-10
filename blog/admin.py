from django.contrib import admin
from django.utils import timezone
from .models import BlogCategory, BlogPost


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class PublishedStatusFilter(admin.SimpleListFilter):
    title = 'publish status'
    parameter_name = 'publish_status'

    def lookups(self, request, model_admin):
        return (
            ('live', 'Published (live)'),
            ('draft', 'Unpublished / draft'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'live':
            return queryset.filter(published_at__isnull=False)
        if self.value() == 'draft':
            return queryset.filter(published_at__isnull=True)
        return queryset


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'author', 'category', 'view_count', 'published_at', 'updated_at')
    list_filter = ('category', PublishedStatusFilter, 'published_at')
    search_fields = ('title', 'slug', 'body')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('author',)
    readonly_fields = ('view_count', 'created_at', 'updated_at')
    actions = ('publish_posts', 'unpublish_posts')
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'author', 'category')}),
        ('Content', {'fields': ('excerpt', 'body', 'hero_image')}),
        ('SEO', {'fields': ('meta_title', 'meta_description')}),
        (
            'Publish',
            {
                'fields': ('published_at',),
                'description': (
                    'Clear “Published at” and save to unpublish, or use Actions → Unpublish selected posts. '
                    'Leave empty for draft; set a date/time (or use Actions → Publish) to go live.'
                ),
            },
        ),
        ('Performance', {'fields': ('view_count',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.action(description='Publish now (set published time to now)')
    def publish_posts(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(published_at=now)
        self.message_user(request, f'{updated} post(s) published.')

    @admin.action(description='Unpublish (remove from site — draft)')
    def unpublish_posts(self, request, queryset):
        updated = queryset.update(published_at=None)
        self.message_user(request, f'{updated} post(s) unpublished (draft).')

    def save_model(self, request, obj, form, change):
        """Respect empty Published at (draft / unpublish); dashboard saves omit this flag and auto-publish when allowed."""
        obj.save(skip_auto_publish=True)
