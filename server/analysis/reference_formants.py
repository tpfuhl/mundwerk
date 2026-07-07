"""Referenz-Formantwerte für deutsche Langvokale und Feedback-Regeln.

Die Zielwerte sind Startwerte aus der Literatur (Größenordnung
Pätzold & Simpson 1997, Kiel Corpus, gelesene Sprache) und bewusst mit
großzügigen Standardabweichungen versehen. Sie sind dazu da, die Pipeline
zu validieren — für den Produktivbetrieb werden sie durch eigene, von
Kirsten kuratierte Referenzdaten ersetzt/verfeinert.

Alle Frequenzen in Hz.
"""

# {phone: {speaker: (f1_mean, f1_sd, f2_mean, f2_sd)}}
TARGETS = {
    "iː": {"male": (280, 45, 2150, 180), "female": (320, 55, 2500, 220)},
    "yː": {"male": (285, 45, 1650, 170), "female": (320, 55, 1900, 200)},
    "uː": {"male": (300, 45, 800, 150), "female": (330, 55, 850, 170)},
    "eː": {"male": (350, 50, 2050, 180), "female": (410, 60, 2350, 210)},
    "øː": {"male": (370, 50, 1500, 160), "female": (430, 60, 1650, 190)},
    "oː": {"male": (370, 50, 780, 140), "female": (420, 60, 820, 160)},
    "aː": {"male": (700, 80, 1250, 160), "female": (850, 100, 1450, 190)},
}

# Sprecherabhängige Obergrenze für die Formantsuche (Praat-Parameter).
MAX_FORMANT = {"male": 5000.0, "female": 5500.0, "child": 8000.0}

# Artikulatorische Merkmale pro Vokal, um generische Hinweise zu formulieren.
#   round: Lippenrundung erwartet?  front: Vorderzungenvokal?
FEATURES = {
    "iː": dict(round=False, front=True),
    "yː": dict(round=True, front=True),
    "uː": dict(round=True, front=False),
    "eː": dict(round=False, front=True),
    "øː": dict(round=True, front=True),
    "oː": dict(round=True, front=False),
    "aː": dict(round=False, front=False),
}

# Spezifische Hinweise für typische Fehler, geprüft vor den generischen
# Regeln. Schlüssel: (phone, dimension, richtung)  mit richtung "high"/"low".
SPECIFIC_FEEDBACK = {
    ("yː", "f2", "low"): (
        "Das klang eher wie ‚u‘. Zungenposition wie bei ‚ie‘ halten "
        "und nur die Lippen runden."
    ),
    ("øː", "f2", "low"): (
        "Das klang eher wie ‚o‘. Zungenposition wie bei ‚ee‘ halten "
        "und nur die Lippen runden."
    ),
    ("uː", "f2", "high"): (
        "Die Zunge ist zu weit vorn oder die Lippen sind zu wenig "
        "gerundet — ‚u‘ wird ganz hinten gebildet, Lippen stark runden."
    ),
    ("iː", "f1", "high"): (
        "Der Mund ist zu weit offen — für ‚ie‘ die Zunge ganz nah an den "
        "Gaumen bringen, fast wie bei ‚j‘."
    ),
    ("aː", "f1", "low"): (
        "Der Mund ist zu geschlossen — für ‚a‘ den Mund weit öffnen, "
        "die Zunge bleibt flach unten."
    ),
}


def _generic_feedback(phone: str, dim: str, direction: str) -> str:
    feats = FEATURES.get(phone, {})
    if dim == "f1":
        if direction == "high":
            return "Der Mund ist zu weit offen bzw. die Zunge zu tief — Zunge etwas anheben."
        return "Der Mund ist zu geschlossen — etwas weiter öffnen."
    # f2
    if direction == "low":
        if feats.get("front"):
            return "Die Zunge ist zu weit hinten — weiter nach vorn schieben."
        return "Die Zunge ist zu weit hinten für diesen Laut."
    if feats.get("round") and not feats.get("front"):
        return "Die Zunge ist zu weit vorn — weiter zurückziehen, Lippen runden."
    return "Die Zunge ist zu weit vorn für diesen Laut."


def feedback_for(phone: str, dim: str, direction: str) -> str:
    """Feedbacktext für eine Abweichung (dim: 'f1'/'f2', direction: 'high'/'low')."""
    return SPECIFIC_FEEDBACK.get(
        (phone, dim, direction), _generic_feedback(phone, dim, direction)
    )
