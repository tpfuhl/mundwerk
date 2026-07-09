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


def measure_segment(formants, start: float,
                    end: float) -> tuple[float, float, float | None]:
    """Median von F1/F2/F3 über das mittlere Drittel von [start, end].

    Gemessen wird bewusst im Zentrum des Segments — an den Rändern steckt
    die Koartikulation (der Folgelaut ist im Formantverlauf schon da).
    F3 (Lippenrundung) ist oft schlechter messbar → None statt Fehler.
    """
    third = (end - start) / 3
    lo, hi = start + third, end - third
    n = 10
    step = (hi - lo) / (n - 1) if n > 1 else 0
    f1s, f2s, f3s = [], [], []
    for i in range(n):
        t = lo + i * step
        f1 = formants.get_value_at_time(1, t)
        f2 = formants.get_value_at_time(2, t)
        f3 = formants.get_value_at_time(3, t)
        if f1 == f1:
            f1s.append(f1)
        if f2 == f2:
            f2s.append(f2)
        if f3 == f3:
            f3s.append(f3)
    if not f1s or not f2s:
        raise AnalysisError("Keine Formanten messbar in diesem Segment.")
    return (statistics.median(f1s), statistics.median(f2s),
            statistics.median(f3s) if f3s else None)


def measure_intensity(snd: parselmouth.Sound, start: float,
                      end: float) -> float | None:
    """Mittlere Intensität (dB) über das mittlere Drittel; None wenn
    nicht messbar. Wird (wie die Dauer) vorerst nur gespeichert —
    Bewertung kommt mit dem Wortakzent (úmfahren/umfáhren)."""
    third = (end - start) / 3
    try:
        intensity = snd.to_intensity(time_step=0.01)
        db = call(intensity, "Get mean", start + third, end - third, "dB")
    except parselmouth.PraatError:
        return None
    return round(db, 1) if db == db else None


def hz_to_bark(f: float) -> float:
    """Hertz → Bark (Traunmüller 1990).

    Das Ohr hört nicht linear, sondern staucht hohe Frequenzen: 100 Hz
    überspannen bei tiefen Frequenzen mehr Bark als bei hohen. Die
    Bark-Skala ist damit die perzeptiv richtige Bühne für den Vergleich
    (Kirstens Punkt „es zählen die relativen Abstände“).

    Ehrlich eingeordnet: Solange die Zielwerte *pro Stimmlage* in Hz
    gepflegt sind und jede Dimension durch ihre eigene (mit-linearisierte)
    Streuung geteilt wird, ist die Ampel nahe am Ziel fast identisch zur
    Hz-Rechnung — Bark ist hier v. a. die saubere Skala und die
    Vorbereitung darauf, die Stimmlagen-Tabellen später durch
    Lobanov-Normalisierung (Onboarding-Kalibrierung) zu ersetzen. Das ist
    der Schritt, der echte Sprecherunabhängigkeit bringt.
    """
    return 26.81 / (1 + 1960.0 / f) - 0.53


def _bark_z(value: float, mean: float, sd: float) -> float:
    """z-Abweichung im Bark-Raum. Die in Hz gepflegte Streuung wird lokal
    linearisiert (bark(mean+sd) − bark(mean)); nahe am Ziel bleibt der
    z-Wert damit praktisch identisch zum Hz-z, sodass die Schwellen
    (GREEN_Z/YELLOW_Z) weiter gelten — Bark ändert nur die Gewichtung
    größerer Abweichungen und über den Vokalraum hinweg."""
    bark_sd = hz_to_bark(mean + sd) - hz_to_bark(mean)
    return (hz_to_bark(value) - hz_to_bark(mean)) / bark_sd


def evaluate(phone: str, f1: float, f2: float,
             target: tuple[float, float, float, float] | None,
             feedback_fn=feedback_for) -> dict:
    """Messwerte gegen Referenz (f1_mean, f1_sd, f2_mean, f2_sd) vergleichen.

    Der Vergleich läuft im Bark-Raum (perzeptiv, s. hz_to_bark), die
    gespeicherten Referenzwerte bleiben in Hz.
    target=None → kein Referenzwert vorhanden, nur Messwerte zurückgeben.
    feedback_fn(phone, dim, direction) liefert die Hinweistexte — das
    Django-Backend reicht hier die DB-kuratierten Regeln (FeedbackRule)
    herein, Default sind die Code-Texte.
    """
    if target is None:
        return {"phone": phone, "f1": round(f1), "f2": round(f2),
                "rating": None, "note": "kein Referenzwert vorhanden"}
    f1_mean, f1_sd, f2_mean, f2_sd = target
    z1 = _bark_z(f1, f1_mean, f1_sd)
    z2 = _bark_z(f2, f2_mean, f2_sd)
    dist = (z1**2 + z2**2) ** 0.5
    rating = "grün" if dist < GREEN_Z else "gelb" if dist < YELLOW_Z else "rot"

    feedback = []
    # Größte Abweichung zuerst kommentieren, nur Abweichungen > 1.5 SD.
    for dim, z in sorted((("f1", z1), ("f2", z2)), key=lambda p: -abs(p[1])):
        if abs(z) > 1.5:
            feedback.append(feedback_fn(phone, dim, "high" if z > 0 else "low"))

    return {
        "phone": phone,
        "f1": round(f1), "f2": round(f2),
        "target_f1": f1_mean, "target_f2": f2_mean,
        "z_f1": round(z1, 2), "z_f2": round(z2, 2),
        "distanz": round(dist, 2),
        "raum": "bark",  # z-Werte/Distanz im Bark-Raum (s. hz_to_bark)
        "rating": rating,
        "feedback": feedback or ["Gut getroffen!"],
    }


def analyze_recording(path: str, phone: str, speaker: str = "male",
                      target: tuple[float, float, float, float] | None = None,
                      segment: tuple[float, float] | None = None,
                      feedback_fn=feedback_for) -> dict:
    """Komplette Pipeline für eine Aufnahme mit einem Zielvokal.

    Ohne `segment` wird der Vokal automatisch gesucht (längster stimmhafter
    Abschnitt) — zuverlässig für isoliert gehaltene Vokale bzw.
    vokaldominante Wörter; sonst kommt das Segment vom MFA-Alignment.
    Ohne `target` werden die eingebauten Literaturwerte benutzt.

    Neben F1/F2 (bewertet) werden F3, Dauer und Intensität gemessen und
    nur gespeichert (Lippenrundung, Quantität, Wortakzent — Bewertung
    folgt in späteren Phasen).
    """
    snd = load_sound(path)
    formants = snd.to_formant_burg(max_number_of_formants=5,
                                   maximum_formant=MAX_FORMANT[speaker])
    start, end = segment if segment else find_voiced_segment(snd)
    f1, f2, f3 = measure_segment(formants, start, end)
    if target is None:
        target = TARGETS.get(phone, {}).get(speaker)
    result = evaluate(phone, f1, f2, target, feedback_fn=feedback_fn)
    result["f3"] = round(f3) if f3 is not None else None
    result["dauer_ms"] = round((end - start) * 1000)
    result["intensitaet_db"] = measure_intensity(snd, start, end)
    result["start"] = round(start, 3)
    result["end"] = round(end, 3)
    return result
