from django.conf import settings
from django.db import models


class Item(models.Model):
    """Ein isolierter Laut, ein Wort oder ein Satz zum Nachsprechen."""

    KIND_CHOICES = [("laut", "laut"), ("wort", "wort"), ("satz", "satz")]

    text = models.CharField(max_length=200)
    ipa = models.CharField(max_length=200, help_text="IPA-Transkription")
    level = models.CharField(max_length=10, default="A1")  # A1..C2
    # "laut" = isoliert gehaltener Laut (kein Alignment, Auto-Segmentierung),
    # "wort"/"satz" = MFA-Alignment. PLAN „Segmentdiagnose“, Schritt 1.
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="wort")
    # Phone(s), auf denen der Übungsfokus liegt, z. B. ["øː"].
    # Phase 1: genau ein Langvokal pro Item.
    focus_segments = models.JSONField(default=list)
    # Soll-Lautung in MFA-Phonen, leerzeichengetrennt ("f ʁ yː") — nur
    # zusammen mit error_variants nötig (Fehlerhypothesen-Alignment).
    mfa_pron = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Soll-Lautung in MFA-Phonen, z. B. „f ʁ yː“")
    # Typische Fehlaussprachen (Kirstens Fehlerhypothesen, gern
    # L1-spezifisch). Einträge: "f l yː" oder
    # {"pron": "f l yː", "hinweis": "Das ‚r‘ klang wie ‚l‘ — …"}.
    error_variants = models.JSONField(
        default=list, blank=True,
        help_text='Liste von Fehlaussprachen, z. B. '
                  '[{"pron": "f l yː", "hinweis": "…"}]')

    def variant_list(self) -> list[tuple[str, str | None]]:
        """error_variants normalisiert → [(pron, hinweis|None)]."""
        out = []
        for v in self.error_variants or []:
            if isinstance(v, str) and v.strip():
                out.append((" ".join(v.split()), None))
            elif isinstance(v, dict) and v.get("pron", "").strip():
                out.append((" ".join(v["pron"].split()), v.get("hinweis")))
        return out

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


class FeedbackRule(models.Model):
    """Kuratierbare Hinweistexte für Formant-Abweichungen (Expertenwissen).

    Didaktische Konvention (Kirsten): Artikulatoren strikt trennen —
    F1 ↔ Mundöffnung, F2 ↔ Zunge horizontal, Rundung ↔ Lippen.
    Per Seed-Migration aus analysis/reference_formants.py befüllt und im
    Admin kuratierbar; fehlt eine Regel, greift der Code-Fallback
    (feedback_for). Änderungen wirken sofort, ohne Deployment.
    """

    DIM_CHOICES = [("f1", "F1 (Mundöffnung)"), ("f2", "F2 (Zunge horizontal)")]
    DIRECTION_CHOICES = [("high", "zu hoch"), ("low", "zu niedrig")]

    phone = models.CharField(max_length=10)  # IPA
    dim = models.CharField(max_length=4, choices=DIM_CHOICES)
    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES)
    text = models.TextField(
        help_text="Hinweis an die Lernenden — Schema „Mund …, Zunge …, "
                  "Lippen …“, die Artikulatoren nicht vermischen.")

    class Meta:
        unique_together = [("phone", "dim", "direction")]

    def __str__(self):
        return f"/{self.phone}/ {self.dim} {self.direction}"


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
    # Vom Sprecher (Korpus-Gruppe) als mustergültig markiert — Grundlage
    # für die Referenzwert-Kalibrierung (manage.py calibrate_targets).
    ist_referenz = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recording #{self.pk} – {self.item.text} ({self.status})"
