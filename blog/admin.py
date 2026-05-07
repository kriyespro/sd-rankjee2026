from django.contrib import admin
from django.utils.text import slugify

from .models import BlogCategory, BlogPost


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'author', 'category', 'view_count', 'published_at', 'updated_at')
    list_filter = ('category', 'published_at')
    search_fields = ('title', 'slug', 'body')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('author',)
    readonly_fields = ('view_count', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'author', 'category')}),
        ('Content', {'fields': ('excerpt', 'body', 'hero_image')}),
        ('SEO', {'fields': ('meta_title', 'meta_description')}),
        ('Publish', {'fields': ('published_at',)}),
        ('Performance', {'fields': ('view_count',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
