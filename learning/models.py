from django.db import models
import re

class ConceptVideo(models.Model):
    skill = models.ForeignKey('assessment.Skill', on_delete=models.CASCADE, null=True, blank=True, related_name='videos', help_text="Link this video to a specific skill")
    title = models.CharField(max_length=200)
    concept_tag = models.CharField(max_length=50)
    video_url = models.URLField(help_text="Paste any YouTube link (watch, youtu.be, or shorts)")
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True, help_text="Upload a custom thumbnail or leave blank for auto YouTube thumbnail")
    duration_seconds = models.IntegerField(default=60)

    def get_video_id(self):
        """Extract the 11-character YouTube video ID from the URL."""
        if not self.video_url:
            return None
        match = re.search(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/)|[?&]v=)([A-Za-z0-9_-]{11})', self.video_url)
        return match.group(1) if match else None

    def get_thumbnail_url(self):
        """Return the priority thumbnail: 1. Manual upload 2. YouTube auto 3. Placeholder"""
        if self.thumbnail:
            return self.thumbnail.url
        
        video_id = self.get_video_id()
        if video_id:
            # hqdefault is reliable across all videos
            return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        
        # Fallback to a nice colored placeholder if everything fails
        return "https://ui-avatars.com/api/?name=Learning&background=6366f1&color=fff&size=512"

    def get_embed_url(self):
        """Convert any YouTube URL to an embed-ready URL."""
        video_id = self.get_video_id()
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}?autoplay=1"
        return self.video_url

    def __str__(self):
        return self.title

