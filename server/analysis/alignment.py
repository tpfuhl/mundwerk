"""Forced Alignment mit dem Montreal Forced Aligner (MFA).

Ruft `mfa align_one` als Subprozess auf (deutsches Akustikmodell +
Lexikon `german_mfa`) und liefert die Phon-Segmente aus dem TextGrid.
Der erste Aufruf nach einem Deployment dauert ~25 s (Modell-/Lexikon-
Cache wird gebaut), danach ~5-10 s pro Aufnahme. Wenn das für die
synchrone API zu langsam wird: Celery-Worker oder MFA-Online-API
(siehe PLAN.md).

Fehlerhypothesen-Alignment (PLAN „Segmentdiagnose“, Schritt 2): Werden
`prons` übergeben (Soll-Lautung + typische Fehlaussprachen), aligniert
MFA gegen ein daraus generiertes Lexikon und wählt die akustisch beste
Variante — `diff_phones` benennt dann die Abweichung von der Soll-Lautung.
Die Phone müssen aus dem Phonset des german_mfa-Modells stammen, sonst
schlägt das Alignment fehl (→ AlignmentError, Aufrufer fällt zurück).

Kein Django-Import hier — auch vom Validierungsskript nutzbar.
"""

import difflib
import os
import subprocess
import tempfile

import parselmouth
from parselmouth.praat import call


class AlignmentError(Exception):
    """Alignment nicht möglich (MFA fehlt, Wort unbekannt, Timeout, …)."""


def segments_from_textgrid(path: str) -> list[tuple[str, float, float]]:
    """Alle Intervalle des 'phones'-Tiers eines TextGrids."""
    tg = parselmouth.read(path)
    n_tiers = call(tg, "Get number of tiers")
    tier = n_tiers  # MFA: letzter Tier ist 'phones'
    for i in range(1, n_tiers + 1):
        if call(tg, "Get tier name", i).lower() in ("phones", "phone"):
            tier = i
            break
    out = []
    for i in range(1, call(tg, "Get number of intervals", tier) + 1):
        label = call(tg, "Get label of interval", tier, i).strip()
        if label and label not in ("sil", "spn", "<eps>", ""):
            out.append((label,
                        call(tg, "Get start time of interval", tier, i),
                        call(tg, "Get end time of interval", tier, i)))
    return out


def align(wav_path: str, text: str, mfa_bin: str,
          timeout: int = 120,
          prons: list[str] | None = None) -> list[tuple[str, float, float]]:
    """Aufnahme gegen die Orthographie alignieren → [(phone, start, end)].

    `mfa_bin` ist der absolute Pfad zum mfa-Binary in seiner conda-Env;
    deren bin/-Verzeichnis wird in den PATH des Subprozesses gehängt
    (MFA braucht openfst & Co. von dort).

    `prons`: Aussprachevarianten für `text` (je ein String mit leerzeichen-
    getrennten MFA-Phonen, die Soll-Lautung zuerst). Statt des german_mfa-
    Lexikons wird dann ein Mini-Lexikon aus genau diesen Varianten benutzt;
    MFA wählt die akustisch beste — Grundlage der Substitutionsdiagnose.
    Nur für Einzelwort-Items sinnvoll.
    """
    if not mfa_bin or not os.path.exists(mfa_bin):
        raise AlignmentError(f"MFA-Binary nicht gefunden: {mfa_bin!r}")

    env = dict(os.environ)
    env["PATH"] = os.path.dirname(mfa_bin) + os.pathsep + env.get("PATH", "")

    with tempfile.TemporaryDirectory(prefix="mfa_") as tmp:
        txt_path = os.path.join(tmp, "utt.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")
        dictionary = "german_mfa"
        if prons:
            dictionary = os.path.join(tmp, "lexicon.txt")
            write_lexicon(dictionary, text, prons)
        tg_path = os.path.join(tmp, "utt.TextGrid")
        cmd = [mfa_bin, "align_one", wav_path, txt_path,
               dictionary, "german_mfa", tg_path, "-q"]
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise AlignmentError(f"MFA-Timeout nach {timeout} s")
        if proc.returncode != 0 or not os.path.exists(tg_path):
            raise AlignmentError(
                f"MFA fehlgeschlagen (Code {proc.returncode}): "
                f"{proc.stderr.strip()[-300:]}")
        segments = segments_from_textgrid(tg_path)
    if not segments:
        raise AlignmentError("Alignment lieferte keine Phon-Segmente.")
    return segments


def write_lexicon(path: str, word: str, prons: list[str]) -> None:
    """MFA-Lexikon mit Aussprachevarianten für ein Wort schreiben.

    MFA normalisiert Text beim Tokenisieren auf Kleinschreibung, daher
    wird das Wort kleingeschrieben eingetragen. Format pro Zeile:
    `wort<TAB>phon phon phon`.
    """
    word = word.strip().lower()
    seen = set()
    with open(path, "w", encoding="utf-8") as f:
        for pron in prons:
            pron = " ".join(pron.split())
            if not pron or pron in seen:
                continue
            seen.add(pron)
            f.write(f"{word}\t{pron}\n")


def diff_phones(soll: list[str], ist: list[str]) -> list[dict]:
    """Abweichungen der gesprochenen von der Soll-Lautfolge benennen.

    → [{typ: ersetzt|fehlt|zuviel, position, soll, ist, text}, …];
    `position` ist der Index in der Soll-Folge, `text` ein deutscher
    Satz fürs Feedback („/l/ statt /ʁ/ gesprochen“).
    """
    out = []
    matcher = difflib.SequenceMatcher(a=soll, b=ist, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        s, i = soll[i1:i2], ist[j1:j2]
        if op == "replace":
            typ = "ersetzt"
            text = f"/{' '.join(i)}/ statt /{' '.join(s)}/ gesprochen"
        elif op == "delete":
            typ = "fehlt"
            text = f"/{' '.join(s)}/ ausgelassen"
        else:  # insert
            typ = "zuviel"
            text = f"/{' '.join(i)}/ zu viel gesprochen"
        out.append({"typ": typ, "position": i1, "soll": s, "ist": i,
                    "text": text})
    return out
