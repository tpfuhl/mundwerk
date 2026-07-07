"""Forced Alignment mit dem Montreal Forced Aligner (MFA).

Ruft `mfa align_one` als Subprozess auf (deutsches Akustikmodell +
Lexikon `german_mfa`) und liefert die Phon-Segmente aus dem TextGrid.
Der erste Aufruf nach einem Deployment dauert ~25 s (Modell-/Lexikon-
Cache wird gebaut), danach ~5-10 s pro Aufnahme. Wenn das für die
synchrone API zu langsam wird: Celery-Worker oder MFA-Online-API
(siehe PLAN.md).

Kein Django-Import hier — auch vom Validierungsskript nutzbar.
"""

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
          timeout: int = 120) -> list[tuple[str, float, float]]:
    """Aufnahme gegen die Orthographie alignieren → [(phone, start, end)].

    `mfa_bin` ist der absolute Pfad zum mfa-Binary in seiner conda-Env;
    deren bin/-Verzeichnis wird in den PATH des Subprozesses gehängt
    (MFA braucht openfst & Co. von dort).
    """
    if not mfa_bin or not os.path.exists(mfa_bin):
        raise AlignmentError(f"MFA-Binary nicht gefunden: {mfa_bin!r}")

    env = dict(os.environ)
    env["PATH"] = os.path.dirname(mfa_bin) + os.pathsep + env.get("PATH", "")

    with tempfile.TemporaryDirectory(prefix="mfa_") as tmp:
        txt_path = os.path.join(tmp, "utt.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")
        tg_path = os.path.join(tmp, "utt.TextGrid")
        cmd = [mfa_bin, "align_one", wav_path, txt_path,
               "german_mfa", "german_mfa", tg_path, "-q"]
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
