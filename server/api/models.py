from django.conf import settings
from django.db import models


class Item(models.Model):
    """Ein Wort oder Satz zum Nachsprechen."""

    text = models.CharField(max_length=200)
    ipa = models.CharField(max_length=200, help_text="IPA-Transkription")
    level = models.CharField(max_length=10, default="A1")  # A1..C2
    # Phone(s), auf denen der Übungsfokus liegt, z. B. ["øː"].
    # Phase 1: genau ein Langvokal pro Item.
    focus_segments = models.JSONField(default=list)

    def __str__(self):
        return f"{self.text} [{self.ipa}]"


class TargetSegment(models.Model):
    """Referenz-Formantwerte pro Phone und Sprechergruppe (Expertenwissen).

    Wird per Seed-Migration aus analysis/reference_formants.py befüllt und
    kann dann im Admin kuratiert werden. Die Feedback-Regeln bleiben
    vorerst im Code (analysis.reference_formants.feedback_for).
    """

    SPEAKER_CHOICES = [("male", "male"), ("female", "female"), ("child", "child")]

    phone = models.CharField(max_length=10)  # IPA
    speaker = models.CharField(max_length=10, choices=SPEAKER_CHOICES)
    f1_mean = models.FloatField()
    f1_sd = models.FloatField()
    f2_mean = models.FloatField()
    f2_sd = models.FloatField()

    class Meta:
        unique_together = [("phone", "speaker")]

    def as_tuple(self):
        return (self.f1_mean, self.f1_sd, self.f2_mean, self.f2_sd)

    def __str__(self):
        return f"/{self.phone}/ ({self.speaker})"


class LearnerProfile(models.Model):
    """Zusatzdaten zum Django-User. Die Muttersprache (ISO 639-1) steuert
    später die L1-spezifischen Übungspfade und Fehlerhypothesen."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="learner_profile")
    native_language = models.CharField(max_length=2)  # z. B. "fr", "en", "it"

    def __str__(self):
        return f"{self.user.username} ({self.native_language})"


class Recording(models.Model):
    """Eine Nutzeraufnahme mit Analyseergebnis."""

    STATUS_CHOICES = [("pending", "pending"), ("done", "done"), ("error", "error")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    audio = models.FileField(upload_to="recordings/%Y/%m/%d/")
    # Bis Nutzerprofile mit Kalibrierung existieren: Sprechergruppe pro Upload.
    speaker = models.CharField(max_length=10, choices=TargetSegment.SPEAKER_CHOICES,
                               default="male")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    result = models.JSONField(null=True, blank=True)  # Formanten + Rating + Feedback
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recording #{self.pk} – {self.item.text} ({self.status})"
