from django.contrib import admin
from .models import ConceptVideo

@admin.register(ConceptVideo)
class ConceptVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'skill', 'concept_tag', 'duration_seconds', 'thumbnail')
    list_filter = ('skill', 'concept_tag')
