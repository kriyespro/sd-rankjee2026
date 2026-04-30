from django.conf import settings
from django.db import models


class StudentDailyClassLog(models.Model):
    class Attendance(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_class_logs",
    )
    log_date = models.DateField(db_index=True)
    topic = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    attendance = models.CharField(
        max_length=10,
        choices=Attendance.choices,
        default=Attendance.ABSENT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-log_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "log_date"], name="uniq_daily_class_log_per_user_date"),
        ]

    def __str__(self):
        return f"{self.user_id} {self.log_date} — {self.topic}"


class SeoTarget(models.Model):
    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        DONE = "DONE", "Done"
        BLOCKED = "BLOCKED", "Blocked"

    class Priority(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    phase = models.CharField(max_length=120)
    title = models.CharField(max_length=255)
    owner = models.CharField(max_length=120, blank=True, default="SEO Team")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-priority", "phase", "id"]

    def __str__(self):
        return f"{self.phase}: {self.title}"
