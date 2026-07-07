"""Framework-freie Analyse-Pipeline: WAV → F1/F2 → Bewertung.

Wird sowohl vom Offline-Validierungsskript (validation/validate.py) als
auch vom Django-Backend (api/) benutzt. Kein Django-Import hier.
"""

import statistics

import parselmouth
from parselmouth.praat import call

from .reference_formants import MAX_FORMANT, TARGETS, feedback_for

# Rating-Schwellen in "kombinierten Standardabweichungen" (euklidische
# Distanz im z-normierten F1/F2-Raum). Bewusst grob — Feintuning kommt
# mit echten Daten.
GREEN_Z = 2.0
YELLOW_Z = 3.5


class AnalysisError(Exception):
    """Aufnahme nicht auswertbar (leer, zu leise, keine Formanten)."""


def load_sound(path: str) -> parselmouth.Sound:
    snd = parselmouth.Sound(path)
    if snd.n_channels > 1:
        snd = snd.convert_to_mono()
    return snd


def find_voiced_segment(snd: parselmouth.Sound) -> tuple[float, float]:
    """Längsten stimmhaften, lauten Abschnitt finden (für Einzelvokale)."""
    pitch = snd.to_pitch(time_step=0.01)
    intensity = snd.to_intensity(time_step=0.01)
    peak = call(intensity, "Get maximum", 0, 0, "Parabolic")
    threshold = peak - 15  # dB unter dem Maximum gilt noch als "laut"

    times = pitch.xs()
    voiced = []
    for t in times:
        f0 = pitch.get_value_at_time(t)
        db = call(intensity, "Get value at time", t, "Cubic")
        voiced.append(f0 == f0 and db == db and db > threshold)  # NaN-sicher

    best, cur_start = None, None
    for i, v in enumerate(voiced):
        if v and cur_start is None:
            cur_start = i
        elif not v and cur_start is not None:
            if best is None or i - cur_start > best[1] - best[0]:
                best = (cur_start, i)
            cur_start = None
    if cur_start is not None and (best is None or len(voiced) - cur_start > best[1] - best[0]):
        best = (cur_start, len(voiced))
    if best is None:
        raise AnalysisError("Kein stimmhafter Abschnitt gefunden — Aufnahme zu leise oder leer?")
    return times[best[0]], times[best[1] - 1]


def measure_segment(formants, start: float, end: float) -> tuple[float, float]:
    """Median von F1/F2 über das mittlere Drittel von [start, end]."""
    third = (end - start) / 3
    lo, hi = start + third, end - third
    n = 10
    step = (hi - lo) / (n - 1) if n > 1 else 0
    f1s, f2s = [], []
    for i in range(n):
        t = lo + i * step
        f1 = formants.get_value_at_time(1, t)
        f2 = formants.get_value_at_time(2, t)
        if f1 == f1:
            f1s.append(f1)
        if f2 == f2:
            f2s.append(f2)
    if not f1s or not f2s:
        raise AnalysisError("Keine Formanten messbar in diesem Segment.")
    return statistics.median(f1s), statistics.median(f2s)


def evaluate(phone: str, f1: float, f2: float,
             target: tuple[float, float, float, float] | None) -> dict:
    """Messwerte gegen Referenz (f1_mean, f1_sd, f2_mean, f2_sd) vergleichen.

    target=None → kein Referenzwert vorhanden, nur Messwerte zurückgeben.
    """
    if target is None:
        return {"phone": phone, "f1": round(f1), "f2": round(f2),
                "rating": None, "note": "kein Referenzwert vorhanden"}
    f1_mean, f1_sd, f2_mean, f2_sd = target
    z1 = (f1 - f1_mean) / f1_sd
    z2 = (f2 - f2_mean) / f2_sd
    dist = (z1**2 + z2**2) ** 0.5
    rating = "grün" if dist < GREEN_Z else "gelb" if dist < YELLOW_Z else "rot"

    feedback = []
    # Größte Abweichung zuerst kommentieren, nur Abweichungen > 1.5 SD.
    for dim, z in sorted((("f1", z1), ("f2", z2)), key=lambda p: -abs(p[1])):
        if abs(z) > 1.5:
            feedback.append(feedback_for(phone, dim, "high" if z > 0 else "low"))

    return {
        "phone": phone,
        "f1": round(f1), "f2": round(f2),
        "target_f1": f1_mean, "target_f2": f2_mean,
        "z_f1": round(z1, 2), "z_f2": round(z2, 2),
        "distanz": round(dist, 2),
        "rating": rating,
        "feedback": feedback or ["Gut getroffen!"],
    }


def analyze_recording(path: str, phone: str, speaker: str = "male",
                      target: tuple[float, float, float, float] | None = None,
                      segment: tuple[float, float] | None = None) -> dict:
    """Komplette Pipeline für eine Aufnahme mit einem Zielvokal.

    Ohne `segment` wird der Vokal automatisch gesucht (längster stimmhafter
    Abschnitt) — bis Forced Alignment (MFA) integriert ist, funktioniert das
    zuverlässig nur für isoliert gehaltene Vokale bzw. vokaldominante Wörter.
    Ohne `target` werden die eingebauten Literaturwerte benutzt.
    """
    snd = load_sound(path)
    formants = snd.to_formant_burg(max_number_of_formants=5,
                                   maximum_formant=MAX_FORMANT[speaker])
    start, end = segment if segment else find_voiced_segment(snd)
    f1, f2 = measure_segment(formants, start, end)
    if target is None:
        target = TARGETS.get(phone, {}).get(speaker)
    result = evaluate(phone, f1, f2, target)
    result["start"] = round(start, 3)
    result["end"] = round(end, 3)
    return result
