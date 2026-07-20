from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class validate_upload_size_mb:
    """FileField validator rejecting files over `max_mb` megabytes."""

    def __init__(self, max_mb):
        self.max_mb = max_mb

    def __call__(self, f):
        limit = self.max_mb * 1024 * 1024
        if f.size > limit:
            raise ValidationError(f'File too large — max {self.max_mb} MB.')

    def __eq__(self, other):
        return isinstance(other, validate_upload_size_mb) and self.max_mb == other.max_mb
