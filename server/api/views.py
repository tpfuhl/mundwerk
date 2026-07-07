from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from analysis.pipeline import AnalysisError, analyze_recording

from .models import Item, Recording, TargetSegment
from .serializers import ItemSerializer, RecordingSerializer


class ItemViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/items/?level=A1 und GET /api/items/{id}/"""

    serializer_class = ItemSerializer

    def get_queryset(self):
        qs = Item.objects.all().order_by("id")
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(level=level)
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

    @staticmethod
    def _analyze(recording):
        results = []
        try:
            for phone in recording.item.focus_segments:
                target = TargetSegment.objects.filter(
                    phone=phone, speaker=recording.speaker).first()
                results.append(analyze_recording(
                    recording.audio.path, phone, recording.speaker,
                    target=target.as_tuple() if target else None))
            recording.result = {"segments": results}
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


class ProfileView(APIView):
    """GET /api/profile/ — Übungsstatistik des angemeldeten Users.

    Aggregiert die Analyseergebnisse pro Vokal: Versuche, mittlere und
    beste Distanz (in kombinierten Standardabweichungen), letztes Rating.
    """

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
        return Response({
            "username": request.user.username,
            "uebungen_gesamt": recordings.count(),
            "phones": phones,
        })
