import logging

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from analysis.alignment import AlignmentError, align, diff_phones
from analysis.pipeline import AnalysisError, analyze_recording
from analysis.reference_formants import feedback_for

from .models import (FeedbackRule, Item, LearnerProfile, Recording,
                     TargetSegment)
from .serializers import (ItemSerializer, ProfileUpdateSerializer,
                          RecordingSerializer, RegisterSerializer,
                          TargetSegmentSerializer)

logger = logging.getLogger(__name__)


class ItemViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/items/?level=A1&kind=laut und GET /api/items/{id}/"""

    serializer_class = ItemSerializer

    def get_queryset(self):
        qs = Item.objects.all().order_by("id")
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(level=level)
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        return qs


class TargetViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/targets/?speaker=male — Referenzformanten aller Laute
    (für die Vokalviereck-Darstellung in der App)."""

    serializer_class = TargetSegmentSerializer

    def get_queryset(self):
        qs = TargetSegment.objects.all().order_by("phone")
        speaker = self.request.query_params.get("speaker")
        if speaker:
            qs = qs.filter(speaker=speaker)
        return qs


class RecordingViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                       mixins.ListModelMixin, viewsets.GenericViewSet):
    """POST /api/recordings/ (multipart: item_id, audio, speaker)
    GET  /api/recordings/{id}/

    Die Analyse läuft derzeit synchron im Request (Parselmouth braucht
    <100 ms pro Aufnahme). Sobald MFA integriert ist (1–3 s pro Alignment),
    wird sie in einen Celery-Task ausgelagert und POST antwortet mit 202.
    """

    serializer_class = RecordingSerializer

    def get_queryset(self):
        # Jeder sieht ausschließlich seine eigenen Aufnahmen.
        return (Recording.objects.filter(user=self.request.user)
                .order_by("-created_at"))

    def perform_create(self, serializer):
        recording = serializer.save(user=self.request.user)
        self._analyze(recording)

    @action(detail=True, methods=["post"])
    def referenz(self, request, pk=None):
        """POST /api/recordings/{id}/referenz/ {"ist_referenz": true|false}

        Markiert die eigene Aufnahme als mustergültig — nur für Mitglieder
        der Korpus-Gruppe (deren Aufnahmen fließen in die Kalibrierung ein).
        """
        if not request.user.groups.filter(name="korpus").exists():
            raise PermissionDenied(
                "Nur Korpus-Mitglieder können Referenzaufnahmen markieren.")
        recording = self.get_object()  # get_queryset: nur eigene Aufnahmen
        recording.ist_referenz = bool(request.data.get("ist_referenz", True))
        recording.save(update_fields=["ist_referenz"])
        return Response(self.get_serializer(recording).data)

    @staticmethod
    def _align(recording):
        """Phon-Segmente per MFA → [(phone, start, end)]; [] wenn MFA aus
        ist, das Item ein isolierter Laut ist oder das Alignment scheitert
        (dann greift die Auto-Segmentierung der Pipeline).

        Hat das Item eine Soll-Lautung (mfa_pron), wird gegen ein Lexikon
        aus Soll-Lautung + Fehlervarianten aligniert — MFA wählt die
        akustisch beste, die Abweichung benennt dann _analyze."""
        item = recording.item
        if not settings.MFA_BIN or item.kind == "laut":
            return []
        prons = None
        # Varianten-Lexikon nur für Einzelwörter — bei Sätzen enthielte
        # es nur ein Wort und das Alignment schlüge fehl.
        if item.mfa_pron and item.kind == "wort":
            prons = [item.mfa_pron] + [p for p, _ in item.variant_list()]
        try:
            return align(recording.audio.path, item.text, settings.MFA_BIN,
                         timeout=settings.MFA_TIMEOUT, prons=prons)
        except AlignmentError as e:
            logger.warning("Alignment-Fallback für Recording %s: %s",
                           recording.pk, e)
            return []

    @staticmethod
    def _lautfolge(item, aligned):
        """Soll/Ist-Lautfolge + benannte Abweichungen fürs Ergebnis-JSON;
        None ohne Soll-Lautung, ohne Alignment oder für Nicht-Wort-Items
        (dort wurde gegen das Standard-Lexikon aligniert, nicht gegen
        die Varianten)."""
        if not aligned or not item.mfa_pron or item.kind != "wort":
            return None
        soll = item.mfa_pron.split()
        ist = [phone for phone, _, _ in aligned]
        abweichungen = diff_phones(soll, ist)
        out = {"soll": soll, "ist": ist, "abweichungen": abweichungen}
        if abweichungen:
            # Kirstens didaktischer Hinweis zur erkannten Fehlervariante
            for pron, hinweis in item.variant_list():
                if pron.split() == ist and hinweis:
                    out["hinweis"] = hinweis
                    break
        return out

    @staticmethod
    def _feedback(phone, dim, direction):
        """Hinweistext aus der DB (Admin-kuratiert), Code-Fallback."""
        rule = FeedbackRule.objects.filter(
            phone=phone, dim=dim, direction=direction).first()
        return rule.text if rule else feedback_for(phone, dim, direction)

    @classmethod
    def _analyze(cls, recording):
        results = []
        try:
            aligned = cls._align(recording)
            by_phone = {}
            for phone, start, end in aligned:
                by_phone.setdefault(phone, (start, end))  # erstes Vorkommen
            for phone in recording.item.focus_segments:
                target = TargetSegment.objects.filter(
                    phone=phone, speaker=recording.speaker).first()
                result = analyze_recording(
                    recording.audio.path, phone, recording.speaker,
                    target=target.as_tuple() if target else None,
                    segment=by_phone.get(phone),
                    feedback_fn=cls._feedback)
                result["segmentierung"] = "mfa" if phone in by_phone else "auto"
                results.append(result)
            recording.result = {"segments": results}
            lautfolge = cls._lautfolge(recording.item, aligned)
            if lautfolge:
                recording.result["lautfolge"] = lautfolge
            recording.status = "done"
        except AnalysisError as e:
            recording.result = {"error": str(e)}
            recording.status = "error"
        recording.save(update_fields=["result", "status"])
        # Audio-Lebenszyklus: Datei wird sofort nach der Analyse gelöscht,
        # das Ergebnis-JSON bleibt. Ausnahme: Mitglieder der Gruppe
        # "korpus" haben zugestimmt, dass ihre Aufnahmen für die
        # Kalibrierung der Referenzwerte aufbewahrt werden.
        keep = (recording.user is not None
                and recording.user.groups.filter(name="korpus").exists())
        if not keep:
            recording.audio.delete(save=True)


class RegisterView(APIView):
    """POST /api/register/ — legt Konto + Token an (einziger offener Endpoint).

    Body: {vorname, nachname, nickname, muttersprache (ISO 639-1)}
    Antwort 201: {token, nickname} — die App speichert den Token dauerhaft;
    er ist das einzige Zugangsmerkmal (kein Passwort, Konto-Upgrade später).
    Rate-Limit gegen Spam: siehe DEFAULT_THROTTLE_RATES["register"].
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.create_user(
            username=data["nickname"],
            first_name=data["vorname"],
            last_name=data["nachname"],
        )  # ohne Passwort → Login nur über den Token
        LearnerProfile.objects.create(
            user=user, native_language=data["muttersprache"].lower())
        token = Token.objects.create(user=user)
        return Response({"token": token.key, "nickname": user.username},
                        status=status.HTTP_201_CREATED)


class ProfileView(APIView):
    """GET /api/profile/ — Übungsstatistik des angemeldeten Users.
    PUT /api/profile/ — Profil editieren (vorname, nachname, muttersprache).

    GET aggregiert die Analyseergebnisse pro Vokal: Versuche, mittlere und
    beste Distanz (in kombinierten Standardabweichungen), letztes Rating.
    PUT ändert nur die Profilfelder — Nickname (username) und Token
    bleiben unverändert.
    """

    def put(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        user.first_name = data["vorname"]
        user.last_name = data["nachname"]
        user.save(update_fields=["first_name", "last_name"])
        learner, _ = LearnerProfile.objects.get_or_create(
            user=user, defaults={"native_language": data["muttersprache"].lower()})
        learner.native_language = data["muttersprache"].lower()
        learner.save(update_fields=["native_language"])
        return self.get(request)

    def get(self, request):
        recordings = (Recording.objects
                      .filter(user=request.user, status="done")
                      .order_by("created_at"))
        stats = {}
        for recording in recordings:
            for seg in (recording.result or {}).get("segments", []):
                if seg.get("distanz") is None:
                    continue
                s = stats.setdefault(seg["phone"], {
                    "phone": seg["phone"], "versuche": 0, "_summe": 0.0,
                    "beste_distanz": None, "letztes_rating": None,
                })
                s["versuche"] += 1
                s["_summe"] += seg["distanz"]
                if s["beste_distanz"] is None or seg["distanz"] < s["beste_distanz"]:
                    s["beste_distanz"] = seg["distanz"]
                s["letztes_rating"] = seg.get("rating")
        phones = []
        for s in sorted(stats.values(), key=lambda s: s["phone"]):
            summe = s.pop("_summe")
            s["mittlere_distanz"] = round(summe / s["versuche"], 2)
            phones.append(s)
        learner = getattr(request.user, "learner_profile", None)
        return Response({
            "username": request.user.username,
            "vorname": request.user.first_name,
            "nachname": request.user.last_name,
            "muttersprache": learner.native_language if learner else None,
            # Korpus-Mitglieder dürfen Aufnahmen als Referenz markieren
            "korpus": request.user.groups.filter(name="korpus").exists(),
            "uebungen_gesamt": recordings.count(),
            "phones": phones,
        })
