"""Tests für Segmentdiagnose und Kurskorrektur „Lautebene zuerst“:
Lautfolgen-Diff, Varianten-Lexikon, Item-Typen, CSV-Import,
DB-kuratierte Feedback-Regeln und die Messgrößen F3/Dauer/Intensität.
MFA-abhängige Pfade werden nicht getestet (→ validation/)."""

import csv
import io
import os
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from parselmouth.praat import call

from analysis.alignment import diff_phones, write_lexicon
from analysis.pipeline import analyze_recording, evaluate, hz_to_bark

from .models import FeedbackRule, Item
from .views import RecordingViewSet


class DiffPhonesTests(TestCase):
    def test_identisch(self):
        self.assertEqual(diff_phones(["f", "ʁ", "yː"], ["f", "ʁ", "yː"]), [])

    def test_substitution_flueh(self):
        # Kirstens Fall: „früh“ als „flüh“ gesprochen
        [d] = diff_phones(["f", "ʁ", "yː"], ["f", "l", "yː"])
        self.assertEqual(d["typ"], "ersetzt")
        self.assertEqual(d["position"], 1)
        self.assertEqual(d["soll"], ["ʁ"])
        self.assertEqual(d["ist"], ["l"])
        self.assertEqual(d["text"], "/l/ statt /ʁ/ gesprochen")

    def test_auslassung(self):
        [d] = diff_phones(["f", "ʁ", "yː"], ["f", "yː"])
        self.assertEqual(d["typ"], "fehlt")
        self.assertEqual(d["text"], "/ʁ/ ausgelassen")

    def test_einfuegung(self):
        [d] = diff_phones(["f", "yː"], ["f", "ʁ", "yː"])
        self.assertEqual(d["typ"], "zuviel")
        self.assertEqual(d["text"], "/ʁ/ zu viel gesprochen")


class WriteLexiconTests(TestCase):
    def test_kleinschreibung_dedupe_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lexicon.txt")
            write_lexicon(path, "Früh", ["f ʁ yː", "f  l yː", "f ʁ yː", ""])
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        self.assertEqual(lines, ["früh\tf ʁ yː", "früh\tf l yː"])


class ItemVariantTests(TestCase):
    def test_variant_list_beide_formen(self):
        item = Item(text="früh", ipa="fʁyː", error_variants=[
            "f  l yː",
            {"pron": "f k yː", "hinweis": "Da war ein ‚k‘ zu hören."},
            {"pron": ""},  # unvollständig → ignorieren
            42,            # Unsinn → ignorieren
        ])
        self.assertEqual(item.variant_list(), [
            ("f l yː", None),
            ("f k yː", "Da war ein ‚k‘ zu hören."),
        ])


class LautfolgeTests(TestCase):
    def setUp(self):
        self.item = Item(
            text="früh", ipa="fʁyː", mfa_pron="f ʁ yː",
            error_variants=[{"pron": "f l yː",
                             "hinweis": "Das ‚r‘ klang wie ‚l‘."}])

    def test_korrekt_gesprochen(self):
        aligned = [("f", 0.0, 0.1), ("ʁ", 0.1, 0.2), ("yː", 0.2, 0.5)]
        lf = RecordingViewSet._lautfolge(self.item, aligned)
        self.assertEqual(lf["abweichungen"], [])
        self.assertNotIn("hinweis", lf)

    def test_fehlervariante_mit_hinweis(self):
        aligned = [("f", 0.0, 0.1), ("l", 0.1, 0.2), ("yː", 0.2, 0.5)]
        lf = RecordingViewSet._lautfolge(self.item, aligned)
        self.assertEqual(lf["ist"], ["f", "l", "yː"])
        self.assertEqual(len(lf["abweichungen"]), 1)
        self.assertEqual(lf["hinweis"], "Das ‚r‘ klang wie ‚l‘.")

    def test_ohne_soll_lautung_kein_diff(self):
        self.item.mfa_pron = ""
        self.assertIsNone(RecordingViewSet._lautfolge(
            self.item, [("f", 0.0, 0.1)]))


class ItemApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester")
        self.client.force_authenticate(self.user)
        Item.objects.create(text="ää", ipa="ɛː", kind="laut",
                            focus_segments=["ɛː"])
        Item.objects.create(text="spät", ipa="ʃpɛːt", kind="wort",
                            focus_segments=["ɛː"])

    def test_kind_filter_und_serialisierung(self):
        data = self.client.get("/api/items/?kind=laut").json()
        laute = [i for i in data if i["text"] == "ää"]
        self.assertEqual(len(laute), 1)
        self.assertEqual(laute[0]["kind"], "laut")
        self.assertTrue(all(i["kind"] == "laut" for i in data))


class ImportItemsTests(TestCase):
    def _import(self, rows, header):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".csv", encoding="utf-8",
                delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
            path = f.name
        try:
            call_command("import_items", path, stdout=io.StringIO())
        finally:
            os.unlink(path)

    def test_neue_spalten(self):
        self._import(
            [["spät", "ʃpɛːt", "A1", "ɛː", "wort", "ʃ p ɛː t",
              "ʃ p l ɛː t | ʃ p ɛː d"],
             ["ie", "iː", "A1", "iː", "laut", "", ""]],
            ["text", "ipa", "level", "focus", "kind", "pron", "varianten"])
        wort = Item.objects.get(text="spät")
        self.assertEqual(wort.kind, "wort")
        self.assertEqual(wort.mfa_pron, "ʃ p ɛː t")
        self.assertEqual([p for p, _ in wort.variant_list()],
                         ["ʃ p l ɛː t", "ʃ p ɛː d"])
        self.assertEqual(Item.objects.get(text="ie").kind, "laut")

    def test_reimport_erhaelt_admin_hinweise(self):
        Item.objects.create(
            text="spät", ipa="ʃpɛːt", mfa_pron="ʃ p ɛː t",
            focus_segments=["ɛː"],
            error_variants=[{"pron": "ʃ p l ɛː t", "hinweis": "Kirstens Text"}])
        self._import(
            [["spät", "ʃpɛːt", "A1", "ɛː", "ʃ p ɛː t", "ʃ p l ɛː t | ʃ p ɛː d"]],
            ["text", "ipa", "level", "focus", "pron", "varianten"])
        item = Item.objects.get(text="spät")
        self.assertEqual(item.variant_list(), [
            ("ʃ p l ɛː t", "Kirstens Text"), ("ʃ p ɛː d", None)])

    def test_alte_csv_ohne_neue_spalten_laesst_felder_stehen(self):
        Item.objects.create(text="spät", ipa="ʃpɛːt", kind="wort",
                            mfa_pron="ʃ p ɛː t", focus_segments=["ɛː"],
                            error_variants=["ʃ p l ɛː t"])
        self._import([["spät", "ʃpɛːt", "A2", "ɛː"]],
                     ["text", "ipa", "level", "focus"])
        item = Item.objects.get(text="spät")
        self.assertEqual(item.level, "A2")          # aktualisiert
        self.assertEqual(item.mfa_pron, "ʃ p ɛː t")   # unangetastet
        self.assertEqual(item.error_variants, ["ʃ p l ɛː t"])


class FeedbackRuleTests(TestCase):
    def test_seed_vollstaendig(self):
        # 7 Vokale × F1/F2 × high/low = 28 Regeln (Seed 0009)
        self.assertEqual(FeedbackRule.objects.count(), 28)

    def test_db_text_vor_code_fallback(self):
        FeedbackRule.objects.filter(
            phone="iː", dim="f1", direction="high").update(
            text="Mund fast schließen (kuratiert).")
        self.assertEqual(
            RecordingViewSet._feedback("iː", "f1", "high"),
            "Mund fast schließen (kuratiert).")

    def test_fallback_wenn_keine_regel(self):
        # Laut ohne Seed-Regel → Code-Fallback (feedback_for), kein Fehler
        text = RecordingViewSet._feedback("ɛː", "f2", "low")
        self.assertIn("Zunge", text)

    def test_evaluate_nutzt_feedback_fn(self):
        result = evaluate("iː", f1=500, f2=2150, target=(280, 45, 2150, 180),
                          feedback_fn=lambda p, d, r: f"FIXTEXT {p} {d} {r}")
        self.assertEqual(result["rating"], "rot")
        self.assertEqual(result["feedback"], ["FIXTEXT iː f1 high"])


class BarkEvaluationTests(TestCase):
    def test_hz_to_bark_monoton(self):
        self.assertLess(hz_to_bark(280), hz_to_bark(800))
        self.assertLess(hz_to_bark(800), hz_to_bark(2200))

    def test_treffer_gruen_und_bark_markiert(self):
        r = evaluate("iː", f1=280, f2=2150, target=(280, 45, 2150, 180))
        self.assertEqual(r["rating"], "grün")
        self.assertEqual(r["raum"], "bark")
        self.assertAlmostEqual(r["z_f1"], 0.0, places=2)

    def test_nahe_am_ziel_wie_hz_z(self):
        # Innerhalb ~1 SD ist der Bark-z praktisch der Hz-z (lokale
        # Linearisierung) — Schwellen bleiben gültig.
        r = evaluate("iː", f1=280 + 45, f2=2150, target=(280, 45, 2150, 180))
        self.assertAlmostEqual(r["z_f1"], 1.0, delta=0.15)

    def test_sd_normierung_konsistent_ueber_vokalraum(self):
        # Weil die Streuung mit-linearisiert wird, ergibt „+2 SD“ überall
        # z≈2 — tiefer wie hoher Vokal. Das ist die belastbare Eigenschaft
        # (keine perzeptive Umgewichtung bei per-Vokal-sd).
        z_tief = evaluate("uː", 300 + 100, 800, (300, 50, 800, 150))["z_f1"]
        z_hoch = evaluate("aː", 700 + 100, 1250, (700, 50, 1250, 150))["z_f1"]
        self.assertAlmostEqual(z_tief, 2.0, delta=0.1)
        self.assertAlmostEqual(z_hoch, 2.0, delta=0.1)


class MeasurementFieldsTests(TestCase):
    """Pipeline liefert F3, Dauer und Intensität (synthetischer Vokal)."""

    def _synth_vowel(self, f1, f2, path, duration=0.5, pitch=120):
        f3 = max(2500.0, f2 + 400)
        kg = call("Create KlattGrid from vowel", "v", duration, pitch,
                  f1, 60, f2, 90, f3, 150, 3500, 0.05, 1000)
        snd = call(kg, "To Sound")
        call(snd, "Scale intensity", 70)
        snd.save(path, "WAV")

    def test_neue_messgroessen_vorhanden(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, "i.wav")
            self._synth_vowel(280, 2150, wav)
            result = analyze_recording(wav, "iː", "male",
                                       target=(280, 45, 2150, 180))
        self.assertIsNotNone(result["f3"])
        self.assertGreater(result["f3"], result["f2"])
        # 0.5 s Vokal, Segment ~ Vollzeit → grob im Bereich
        self.assertGreater(result["dauer_ms"], 200)
        self.assertIsNotNone(result["intensitaet_db"])
        self.assertEqual(result["rating"], "grün")
