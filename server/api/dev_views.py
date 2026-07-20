"""Interne Testkonsole für neue Features — kein API-Client/Token nötig.

Nur eingebunden, wenn DEBUG=True (siehe config/urls.py). Zugriff über
die normale Django-Admin-Session (staff_member_required). Die Aufnahme
läuft exakt durch dieselbe Pipeline wie die App
(RecordingViewSet._align/_analyze), damit hier getestete Änderungen
1:1 auch fürs Handy gelten — kein zweiter Codepfad.
"""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Item, Recording, TargetSegment
from .views import RecordingViewSet


@staff_member_required
def console(request):
    if request.method == "POST":
        item = get_object_or_404(Item, pk=request.POST.get("item_id"))
        audio = request.FILES.get("audio")
        if not audio:
            messages.error(request, "Bitte eine Audiodatei auswählen.")
            return redirect("dev-console")
        recording = Recording.objects.create(
            user=request.user, item=item, audio=audio,
            speaker=request.POST.get("speaker", "male"))
        RecordingViewSet._analyze(recording)
        return redirect("dev-result", pk=recording.pk)

    context = {
        "items": Item.objects.all().order_by("level", "text"),
        "speakers": TargetSegment.SPEAKER_CHOICES,
        "recent": Recording.objects.filter(user=request.user)
                            .order_by("-created_at")[:15],
    }
    return render(request, "dev/console.html", context)


@staff_member_required
def result(request, pk):
    # Nur eigene Testläufe sichtbar — dieselbe Isolation wie in der API.
    recording = get_object_or_404(Recording, pk=pk, user=request.user)
    return render(request, "dev/result.html", {"recording": recording})
