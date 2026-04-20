from django.db import models
from django.conf import settings
import uuid

class SkillPath(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    level_order = models.IntegerField(default=1, help_text="e.g. 1=Beginner, 2=Pro, 3=Earner")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['level_order']

    def __str__(self):
        return f"{self.name} (Level {self.level_order})"

class Skill(models.Model):
    path = models.ForeignKey(SkillPath, on_delete=models.SET_NULL, null=True, blank=True, related_name='skills')
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.PositiveIntegerField(default=0, help_text="Order in the learning sequence")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']

    def get_next_skill(self):
        """Find the next active skill in the same path."""
        if not self.path:
            return None
        return Skill.objects.filter(
            path=self.path,
            is_active=True,
            order__gt=self.order
        ).order_by('order', 'id').first()

    def __str__(self):
        return f"{self.order}. {self.name}"

    def partition_questions(self):
        """
        Organizes all questions for this skill into QuestionSets of 10.
        Sorted by difficulty: EASY -> MEDIUM -> HARD.
        """
        from django.db.models import Case, When, Value, IntegerField
        
        questions = list(self.questions.all().order_by(
            Case(
                When(difficulty='EASY', then=Value(1)),
                When(difficulty='MEDIUM', then=Value(2)),
                When(difficulty='HARD', then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            ),
            'id'
        ))
        
        if not questions:
            return 0
            
        # Optional: Smart strategy could preserve old set IDs if they have 10,
        # but for now, deletion is safest for ensuring difficulty order across all levels.
        self.sets.all().delete()
        
        chunk_size = 10
        created_sets = 0
        for i in range(0, len(questions), chunk_size):
            set_num = (i // chunk_size) + 1
            chunk = questions[i:i + chunk_size]
            
            # Use the difficulty of the first question as a label
            avg_diff = chunk[0].difficulty
            
            q_set = QuestionSet.objects.create(
                skill=self,
                name=f"Level {set_num} - {avg_diff.title()}",
                order=set_num
            )
            # Efficiently link questions to the new set
            from django.db import transaction
            with transaction.atomic():
                for q in chunk:
                    q.question_set = q_set
                    q.save(update_fields=['question_set'])
            created_sets += 1
        return created_sets

class QuestionSet(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='sets')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.skill.name} - {self.name}"

class Question(models.Model):
    DIFFICULTY_CHOICES = (
        ('EASY', 'Easy'),
        ('MEDIUM', 'Medium'),
        ('HARD', 'Hard'),
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='questions')
    question_set = models.ForeignKey(QuestionSet, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    source_video = models.ForeignKey(
        'learning.ConceptVideo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_questions',
        help_text='If set, this question is linked to a specific learning video import.',
    )
    is_video_import = models.BooleanField(default=False, db_index=True)
    text = models.TextField()
    concept_tag = models.CharField(max_length=50) # e.g. "SEO", "Facebook Ads"
    explanation = models.TextField(blank=True, help_text="Explanation of the correct answer shown upon failing")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='EASY')
    
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    option_c = models.CharField(max_length=200)
    option_d = models.CharField(max_length=200)
    
    correct_option = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])

    def __str__(self):
        return self.text[:50]

class UserAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    time_taken_seconds = models.IntegerField(default=0)
    passed = models.BooleanField(default=False) # >80% to pass
    weak_concepts = models.JSONField(default=list) # List of failed concept tags
    attempt_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.skill.name} - {self.score}%"

class UserSetAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question_set = models.ForeignKey(QuestionSet, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    time_taken_seconds = models.IntegerField(default=0)
    passed = models.BooleanField(default=False)
    attempt_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.question_set.name} - {self.score}%"

class DailyJackpot(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='jackpots')
    scheduled_time = models.DateTimeField(help_text="Time when the jackpot quiz goes live (e.g. 9:00 PM)")
    prize_pool = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_time']

    def __str__(self):
        return f"Jackpot: {self.skill.name} @ {self.scheduled_time.strftime('%Y-%m-%d %H:%M')}"

class JackpotWinner(models.Model):
    jackpot = models.ForeignKey(DailyJackpot, on_delete=models.CASCADE, related_name='winners')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rank = models.PositiveIntegerField()
    score = models.IntegerField()
    time_taken_seconds = models.IntegerField()
    award_amount = models.DecimalField(max_digits=10, decimal_places=2)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rank']
        unique_together = ('jackpot', 'user')

    def __str__(self):
        return f"#{self.rank} - {self.user.username} (₹{self.award_amount})"

class Certificate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='certificates')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    certificate_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate: {self.user.username} - {self.skill.name}"


class SkillTestEntitlement(models.Model):
    """Server-side record that this user already paid (trial/wallet) for an open test for this skill."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skill_test_entitlements')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='test_entitlements')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'skill'], name='uniq_skill_test_entitlement_user_skill'),
        ]

    def __str__(self):
        return f"{self.user_id} → {self.skill_id}"
