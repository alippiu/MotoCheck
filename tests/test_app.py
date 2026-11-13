import json
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from app import app
from motocheck.catalog import CATALOG, SOURCES, SYMPTOMS, build_vehicle
from motocheck.diagnosis import (
    QUESTIONS,
    QUESTION_SYMPTOMS,
    RULES,
    SAFETY_SYMPTOMS,
    diagnose,
    symptom_questions,
    validate_rule_evidence,
)
from motocheck.workshops import clear_cache


def vehicle_form(**overrides):
    data = {
        "brand": "honda",
        "model": "",
        "variant": "",
        "year": "",
        "category": "other",
        "transmission": "unknown",
        "fuel_system": "unknown",
        "cooling_system": "unknown",
        "final_drive": "unknown",
        "brakes": "unknown",
    }
    data.update(overrides)
    return data


def load_json_without_duplicate_keys(path):
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"JSON key appears more than once: {key}")
            result[key] = value
        return result

    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )


class FakeResponse:
    def __init__(self, value, status_code=200):
        self.value = value
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error

    def json(self):
        return self.value


class MotoCheckTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        clear_cache()

    def test_home_and_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"MOTO", response.data)
        self.assertIn(b"Identitas kendaraan", response.data)
        self.assertIn(b"Panduan", response.data)
        self.assertIn(b"Cari Bengkel", response.data)
        self.assertIn(b"KNOW YOUR MACHINE.", response.data)
        self.assertIn(b"RIDE WITH CONFIDENCE.", response.data)
        self.assertIn(b"Mulai Pemeriksaan", response.data)
        self.assertIn(b"data-symptom-search", response.data)
        self.assertIn(b'aria-current="page"', response.data)
        self.assertIn(b'name="symptoms"', response.data)
        self.assertIn(
            b"0 gejala memiliki aturan manual resmi untuk model/tahun tertentu",
            response.data,
        )
        self.assertIn(b"24 hanya memiliki panduan umum", response.data)
        self.assertIn(b"7 belum memiliki aturan analisis memadai", response.data)
        css = self.client.get("/static/css/style.css")
        wizard = self.client.get("/static/js/wizard.js")
        self.assertEqual(css.status_code, 200)
        self.assertEqual(wizard.status_code, 200)
        illustration = self.client.get("/static/images/garage-bike.svg")
        self.assertEqual(illustration.status_code, 200)
        self.assertIn("image/svg+xml", illustration.content_type)
        self.assertIn(b"Ilustrasi sepeda motor MotoCheck", illustration.data)
        css.close()
        wizard.close()
        illustration.close()

    def test_vehicle_catalog_is_cautious_and_complete(self):
        response = self.client.get("/")
        for brand in ("Honda", "Yamaha", "Suzuki", "Kawasaki"):
            self.assertIn(brand.encode(), response.data)
        result = self.client.post(
            "/periksa",
            data={**vehicle_form(), "symptoms": ["sulit_dihidupkan"]},
        )
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Belum dikonfirmasi", result.data)
        self.assertIn(b"belum diverifikasi", result.data)

    def test_json_data_has_no_duplicate_keys_and_rules_resolve_sources(self):
        data_directory = Path(__file__).parents[1] / "motocheck" / "data"
        for path in data_directory.glob("*.json"):
            with self.subTest(file=path.name):
                load_json_without_duplicate_keys(path)

        for rule in RULES:
            with self.subTest(rule=rule["rule_id"]):
                self.assertIn(rule["source_id"], SOURCES)
                source = SOURCES[rule["source_id"]]
                self.assertTrue(source["title"])
                self.assertTrue(source["publisher"])
                self.assertIn("url", source)
                self.assertTrue(rule["source_section"])
                self.assertIn("source_page", rule)
                self.assertEqual(rule["evidence_status"], "general_guide")
                self.assertEqual(source["kind"], "heuristic")
                self.assertIsNone(source["url"])
                self.assertFalse(source["content_reviewed"])

    def test_external_evidence_requires_reviewed_document_and_exact_scope(self):
        source = {
            "title": "Owner's Manual",
            "publisher": "Yamaha Motor",
            "url": "https://example.com/manual.pdf",
            "kind": "manufacturer_owner_manual",
            "content_reviewed": True,
            "section": "Troubleshooting",
            "coverage": [{"catalog_model_id": "honda_beat_street", "year": 2024}],
            "verified_rule_claims": {
                "example_rule": "Manual troubleshooting lists this symptom and check."
            },
        }
        rule = {
            "rule_id": "example_rule",
            "evidence_status": "external_verified",
            "source_id": "example_manual",
            "source_section": "Troubleshooting",
            "source_page": 42,
            "verified_scope": [{"catalog_model_id": "honda_beat_street", "year": 2024}],
            "evidence_claim": "The manual links the reported symptom to the listed check.",
            "evidence_note": "Applies only to the exact model and model year shown.",
            "symptoms": ["tarikan_berat"],
        }
        validate_rule_evidence([rule], {"example_manual": source})

        invalid_source = {**source, "kind": "owner_manual_portal"}
        with self.assertRaisesRegex(ValueError, "bukti manual"):
            validate_rule_evidence([rule], {"example_manual": invalid_source})

        invalid_scope = {
            **rule,
            "verified_scope": [{"catalog_model_id": "yamaha_nmax_turbo", "year": 2024}],
        }
        with self.assertRaisesRegex(ValueError, "bukti manual"):
            validate_rule_evidence([invalid_scope], {"example_manual": source})

        general_as_external = {
            **RULES[0],
            "evidence_status": "external_verified",
        }
        with self.assertRaisesRegex(ValueError, "bukti manual"):
            validate_rule_evidence([general_as_external], SOURCES)

    def test_external_rule_is_limited_to_verified_vehicle_model_and_year(self):
        from motocheck.diagnosis import _rule_matches

        rule = {
            "rule_id": "example_rule",
            "evidence_status": "external_verified",
            "verified_scope": [{"catalog_model_id": "honda_beat_street", "year": 2024}],
            "symptoms": ["tarikan_berat"],
            "configuration": {},
        }
        vehicle = build_vehicle(
            vehicle_form(
                brand="honda",
                model="honda_beat_street",
                variant="other",
            )
        )
        self.assertIsNone(_rule_matches(rule, {"tarikan_berat"}, vehicle))

        covered_vehicle = build_vehicle(
            vehicle_form(
                brand="honda",
                model="honda_beat_street",
                variant="2024",
            )
        )
        self.assertEqual(
            _rule_matches(rule, {"tarikan_berat"}, covered_vehicle),
            {"tarikan_berat"},
        )

        wrong_model = build_vehicle(
            vehicle_form(
                brand="yamaha",
                model="yamaha_nmax_turbo",
                variant="tech_max",
            )
        )
        self.assertIsNone(_rule_matches(rule, {"tarikan_berat"}, wrong_model))

    def test_verified_models_apply_only_documented_configuration(self):
        self.assertEqual(len(CATALOG["models"]), 5)
        self.assertEqual(sum(len(model["variants"]) for model in CATALOG["models"]), 13)
        for model in CATALOG["models"]:
            self.assertIn(model["brand_id"], {brand["id"] for brand in CATALOG["brands"]})
            self.assertIn(model["source_id"], SOURCES)
            self.assertTrue(SOURCES[model["source_id"]]["url"].startswith("https://"))
            self.assertTrue(model["year_note"])

        yamaha = build_vehicle(
            vehicle_form(
                brand="yamaha",
                model="yamaha_nmax_turbo",
                variant="tech_max",
            )
        )
        self.assertEqual(yamaha["model"], "NMAX TURBO")
        self.assertEqual(yamaha["configuration_ids"]["transmission"], "cvt")
        self.assertEqual(yamaha["configuration_ids"]["category"], "other")
        self.assertEqual(yamaha["year"], "Tidak diketahui")
        self.assertIn("yamaha-motor.co.id", yamaha["model_source"]["url"])
        report = self.client.post(
            "/periksa",
            data={
                **vehicle_form(
                    brand="yamaha",
                    model="yamaha_nmax_turbo",
                    variant="tech_max",
                ),
                "symptoms": ["tarikan_berat"],
                "situation": "acceleration",
            },
        )
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"NMAX TURBO - Yamaha Motor Indonesia", report.data)
        self.assertIn(b"https://www.yamaha-motor.co.id/product/nmax-turbo/", report.data)
        self.assertIn(b"Situasi gejala", report.data)
        self.assertIn(b"<dt>Transmisi</dt>", report.data)
        self.assertNotIn(b"<dt>Category</dt>", report.data)
        self.assertNotIn(b"<dt>Transmission</dt>", report.data)

        suzuki = build_vehicle(
            vehicle_form(
                brand="suzuki",
                model="suzuki_gsx_r150",
                variant="abs",
            )
        )
        self.assertEqual(suzuki["configuration_ids"]["brakes"], "abs")
        self.assertEqual(suzuki["configuration_ids"]["transmission"], "unknown")
        self.assertIn("suzuki.co.id", suzuki["model_source"]["url"])

        fazzio = build_vehicle(
            vehicle_form(
                brand="yamaha",
                model="yamaha_fazzio",
                variant="hybrid_lux",
            )
        )
        self.assertEqual(fazzio["configuration_ids"]["transmission"], "automatic_belt")
        self.assertEqual(fazzio["configuration_ids"]["fuel_system"], "injection")
        self.assertEqual(fazzio["configuration_ids"]["cooling_system"], "air")
        self.assertEqual(fazzio["configuration_ids"]["front_brake"], "disc")
        self.assertEqual(fazzio["configuration_ids"]["rear_brake"], "drum")
        self.assertEqual(fazzio["configuration_ids"]["brakes"], "unknown")
        self.assertEqual(fazzio["year"], "Tidak diketahui")
        self.assertIn("yamaha-motor.co.id/product/fazzio", fazzio["model_source"]["url"])

        gsx_s150 = build_vehicle(
            vehicle_form(
                brand="suzuki",
                model="suzuki_gsx_s150",
                variant="keyless",
            )
        )
        self.assertEqual(gsx_s150["configuration_ids"]["transmission"], "unknown")
        self.assertEqual(gsx_s150["configuration_ids"]["fuel_system"], "unknown")
        self.assertEqual(gsx_s150["configuration_ids"]["front_brake"], "unknown")

        honda = build_vehicle(
            vehicle_form(
                brand="honda",
                model="honda_beat_street",
                variant="2024",
            )
        )
        self.assertEqual(honda["year"], "2024")
        self.assertTrue(honda["year_verified"])
        self.assertEqual(honda["configuration_ids"]["transmission"], "unknown")
        self.assertIn("hondamotopub.com/model/AHJ/K1A240", honda["model_source"]["url"])
        with self.assertRaisesRegex(ValueError, "tidak sesuai"):
            build_vehicle(
                vehicle_form(
                    brand="honda",
                    model="honda_beat_street",
                    variant="2024",
                    year="2022",
                )
            )

        with self.assertRaisesRegex(ValueError, "konfigurasi"):
            build_vehicle(
                vehicle_form(
                    brand="yamaha",
                    model="yamaha_fazzio",
                    variant="hybrid_lux",
                    front_brake="<script>",
                )
            )

        with self.assertRaisesRegex(ValueError, "tidak sesuai"):
            build_vehicle(
                vehicle_form(brand="honda", model="yamaha_nmax_turbo", variant="tech_max")
            )
        unknown = build_vehicle(
            vehicle_form(
                brand="honda",
                model="other",
                model_custom="Model tidak terdaftar",
                variant="other",
            )
        )
        self.assertIsNone(unknown["model_source"])
        self.assertEqual(unknown["configuration_ids"]["transmission"], "unknown")

    def test_every_catalog_variant_builds_with_declared_source_and_known_values(self):
        source_fields = {
            "category": "categories",
            "transmission": "transmissions",
            "fuel_system": "fuel_systems",
            "cooling_system": "cooling_systems",
            "final_drive": "final_drives",
            "brakes": "brakes",
            "front_brake": "brake_types",
            "rear_brake": "brake_types",
        }
        for model in CATALOG["models"]:
            for variant in model["variants"]:
                with self.subTest(model=model["id"], variant=variant["id"]):
                    source_id = variant.get("source_id", model["source_id"])
                    self.assertIn(source_id, SOURCES)
                    self.assertTrue(SOURCES[source_id]["url"].startswith("https://"))
                    vehicle = build_vehicle(
                        vehicle_form(
                            brand=model["brand_id"],
                            model=model["id"],
                            variant=variant["id"],
                        )
                    )
                    for field, options_key in source_fields.items():
                        allowed = {item["id"] for item in CATALOG[options_key]}
                        self.assertIn(vehicle["configuration_ids"][field], allowed)

    def test_verified_and_user_entered_configuration_provenance_is_separate(self):
        known_model = build_vehicle(
            vehicle_form(
                brand="yamaha",
                model="yamaha_fazzio",
                variant="hybrid_lux",
                fuel_system="carburetor",
            )
        )
        self.assertEqual(known_model["configuration_ids"]["fuel_system"], "injection")
        self.assertEqual(known_model["configuration_provenance"]["fuel_system"], "Tercantum pada sumber resmi")
        self.assertEqual(known_model["user_configuration"]["fuel_system"], "Karburator")

        user_model = build_vehicle(
            vehicle_form(
                brand="honda",
                model="other",
                model_custom="Model saya",
                transmission="manual_clutch",
            )
        )
        self.assertEqual(user_model["configuration_ids"]["transmission"], "manual_clutch")
        self.assertEqual(user_model["configuration_provenance"]["transmission"], "Isian pengguna")

    def test_legacy_matic_and_manual_drive_rules_remain_available(self):
        matic = self.client.post(
            "/periksa",
            data={"jenis_motor": "matic", "gejala": "tarikan_berat"},
        )
        manual = self.client.post(
            "/periksa",
            data={"jenis_motor": "manual", "gejala": "tarikan_berat"},
        )
        self.assertEqual(matic.status_code, 200)
        self.assertEqual(manual.status_code, 200)
        self.assertIn(b"Area CVT mungkin perlu diperiksa", matic.data)
        self.assertIn(b"Kopling, perpindahan gigi", manual.data)

    def test_diagnostic_result_and_questions(self):
        response = self.client.post(
            "/periksa",
            data={
                **vehicle_form(transmission="cvt"),
                "symptoms": ["sulit_dihidupkan", "aki_lemah"],
                "starter": "weak",
                "indicator": "weak_battery",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Aki atau rangkaian starter perlu diperiksa", response.data)
        self.assertIn(b"Starter", response.data)
        self.assertIn(b"Lampu/klakson ikut melemah", response.data)
        self.assertIn(b"Respons starter", response.data)
        self.assertIn(b"Indikator atau perangkat listrik", response.data)
        self.assertIn(b"Perlu Diperiksa", response.data)
        self.assertIn(b"Pemeriksaan awal, bukan penetapan kerusakan pasti", response.data)
        self.assertIn(b"Gejala utama:", response.data)
        self.assertIn(b"Gejala tambahan:", response.data)
        self.assertIn(b"Panduan umum", response.data)
        self.assertIn(b"Bukti teknis belum cukup", response.data)
        self.assertIn(b"Cakupan sumber:", response.data)
        self.assertIn(b"Tidak spesifik model atau tahun", response.data)
        self.assertIn(b"Tidak ada kandidat yang didukung isi manual resmi", response.data)
        self.assertNotIn(b"akurasi", response.data.lower())

    def test_answers_and_known_transmission_change_candidate_order_and_scope(self):
        unknown_vehicle = build_vehicle(vehicle_form())
        electrical_support = diagnose(
            ["sulit_dihidupkan"],
            {"starter": "weak", "indicator": "weak_battery"},
            unknown_vehicle,
        )
        electrical_conflict = diagnose(
            ["sulit_dihidupkan"],
            {"starter": "normal", "indicator": "none"},
            unknown_vehicle,
        )
        self.assertEqual(electrical_support["candidates"][0]["rule_id"], "start_battery")
        self.assertEqual(electrical_conflict["candidates"][0]["rule_id"], "start_fuel_ignition")
        self.assertIn("Mendukung kecocokan aturan umum", electrical_support["candidates"][0]["question_effects"][0]["effect"])
        self.assertIn("lebih lemah", electrical_conflict["candidates"][0]["question_effects"][0]["effect"])

        nmax = build_vehicle(
            vehicle_form(
                brand="yamaha",
                model="yamaha_nmax_turbo",
                variant="tech_max",
            )
        )
        fazzio = build_vehicle(
            vehicle_form(
                brand="yamaha",
                model="yamaha_fazzio",
                variant="hybrid_lux",
            )
        )
        nmax_result = diagnose(["tarikan_berat"], {"situation": "acceleration"}, nmax)
        fazzio_result = diagnose(["tarikan_berat"], {"situation": "acceleration"}, fazzio)
        self.assertIn("drive_cvt", {item["rule_id"] for item in nmax_result["candidates"]})
        self.assertNotIn("drive_cvt", {item["rule_id"] for item in fazzio_result["candidates"]})
        self.assertEqual(
            fazzio["configuration_provenance"]["transmission"],
            "Tercantum pada sumber resmi",
        )
        self.assertIn("Bukti teknis belum cukup", fazzio_result["message"])

    def test_primary_symptom_is_explicit_and_must_be_selected(self):
        response = self.client.post(
            "/periksa",
            data={
                **vehicle_form(),
                "symptoms": ["lampu_redup", "tarikan_berat"],
                "primary_symptom": "tarikan_berat",
                "situation": "acceleration",
                "indicator": "weak_battery",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<strong>Gejala utama:</strong> Tarikan motor terasa berat", response.data)
        self.assertIn(b"<strong>Gejala tambahan:</strong> Lampu motor redup", response.data)

        invalid = self.client.post(
            "/periksa",
            data={
                **vehicle_form(),
                "symptoms": ["lampu_redup"],
                "primary_symptom": "mesin_panas",
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn(b"gejala utama", invalid.data.lower())

    def test_follow_up_effects_and_source_scope_are_explained(self):
        response = self.client.post(
            "/periksa",
            data={
                **vehicle_form(),
                "symptoms": ["sulit_dihidupkan", "aki_lemah"],
                "starter": "weak",
                "indicator": "weak_battery",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pengaruh jawaban terhadap aturan", response.data)
        self.assertIn(b"Mendukung kecocokan aturan umum", response.data)
        self.assertIn(b"Heuristik internal MotoCheck", response.data)
        self.assertIn(b"tidak membuktikan", response.data.lower())

        weaker = self.client.post(
            "/periksa",
            data={
                **vehicle_form(),
                "symptoms": ["sulit_dihidupkan"],
                "starter": "normal",
                "indicator": "none",
            },
        )
        self.assertEqual(weaker.status_code, 200)
        self.assertIn(b"Tidak selaras; dugaan ini menjadi lebih lemah", weaker.data)

    def test_brakes_overheat_and_fuel_leak_are_stop_urgency(self):
        cases = [
            ("rem_kurang_pakem", "Jangan Dikendarai"),
            ("mesin_panas", "Jangan membongkar mesin atau membuka tutup radiator saat panas"),
            ("kebocoran_oli", "tidak membuat dugaan penyebab"),
            ("kebocoran_bahan_bakar", "Jangan hidupkan motor, jauhkan dari api"),
            ("gangguan_kemudi", "Jangan Dikendarai"),
        ]
        for symptom_id, expected in cases:
            with self.subTest(symptom=symptom_id):
                response = self.client.post(
                    "/periksa",
                    data={**vehicle_form(), "symptoms": [symptom_id]},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Jangan Dikendarai", response.data)
                self.assertIn(expected.encode(), response.data)
                self.assertIn(b"Jangan dikendarai ke bengkel", response.data)

    def test_every_safety_symptom_requires_stopping(self):
        for symptom_id in SAFETY_SYMPTOMS:
            with self.subTest(symptom=symptom_id):
                response = self.client.post(
                    "/periksa",
                    data={**vehicle_form(), "symptoms": [symptom_id]},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Jangan Dikendarai", response.data)
                self.assertIn(b"Jangan dikendarai ke bengkel", response.data)

    def test_unsupported_symptom_returns_evidence_insufficient(self):
        response = self.client.post(
            "/periksa",
            data={**vehicle_form(), "symptoms": ["asap_abnormal"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Bukti belum cukup", response.data)
        self.assertIn(b"tidak membuat dugaan penyebab", response.data)

    def test_every_symptom_can_be_submitted_without_inventing_missing_rules(self):
        for symptom in SYMPTOMS:
            with self.subTest(symptom=symptom["id"]):
                response = self.client.post(
                    "/periksa",
                    data={**vehicle_form(), "symptoms": [symptom["id"]]},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(symptom["name"].encode(), response.data)
                if symptom["id"] not in {
                    symptom_id for rule in RULES for symptom_id in rule["symptoms"]
                }:
                    self.assertIn(b"Bukti belum cukup", response.data)

    def test_follow_up_answers_change_candidate_order(self):
        with_specific_answer = self.client.post(
            "/periksa",
            data={
                **vehicle_form(),
                "symptoms": ["sulit_dihidupkan"],
                "starter": "weak",
                "indicator": "weak_battery",
            },
        )
        without_specific_answer = self.client.post(
            "/periksa",
            data={
                **vehicle_form(),
                "symptoms": ["sulit_dihidupkan"],
                "starter": "normal",
                "indicator": "none",
                "when": "cold",
            },
        )
        self.assertLess(
            with_specific_answer.data.index(b"Aki atau rangkaian starter perlu diperiksa"),
            with_specific_answer.data.index(b"Sistem bahan bakar atau pengapian perlu pemeriksaan"),
        )
        self.assertLess(
            without_specific_answer.data.index(b"Sistem bahan bakar atau pengapian perlu pemeriksaan"),
            without_specific_answer.data.index(b"Aki atau rangkaian starter perlu diperiksa"),
        )

    def test_only_questions_used_by_matching_rules_are_shown(self):
        questions = symptom_questions({"tarikan_berat"})
        self.assertEqual(set(questions), {"situation"})
        self.assertNotIn("after", QUESTIONS)
        self.assertNotIn("frequency", QUESTIONS)
        self.assertNotIn("smoke", QUESTIONS)
        self.assertEqual(symptom_questions({"asap_abnormal"}), {})
        for question_id, symptoms in QUESTION_SYMPTOMS.items():
            if symptoms:
                self.assertTrue(
                    any(
                        question_id in rule["conditions"]
                        and symptoms.intersection(rule["symptoms"])
                        for rule in RULES
                    )
                )

    def test_invalid_or_dangerous_form_data_is_rejected_or_escaped(self):
        for data in (
            {},
            vehicle_form(),
            {**vehicle_form(), "symptoms": ["not_a_symptom"]},
            {**vehicle_form(), "symptoms": ["sulit_dihidupkan"], "starter": "javascript:alert(1)"},
            {**vehicle_form(), "symptoms": ["sulit_dihidupkan"], "brand": "<script>alert(1)</script>"},
            {**vehicle_form(), "symptoms": ["sulit_dihidupkan"], "year": "2022x"},
            {**vehicle_form(), "symptoms": ["sulit_dihidupkan"], "sound": "other"},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.client.post("/periksa", data=data).status_code, 400)

        escaped = self.client.post(
            "/periksa",
            data={**vehicle_form(model="<script>alert(1)</script>"), "symptoms": ["brebet"]},
        )
        self.assertEqual(escaped.status_code, 200)
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", escaped.data)
        self.assertNotIn(b"<script>alert(1)</script>", escaped.data)

    def test_rule_source_ids_are_defined_and_symptoms_are_valid(self):
        self.assertEqual(len(RULES), 11)
        for rule in RULES:
            self.assertIn(rule["source_id"], SOURCES)
            self.assertEqual(SOURCES[rule["source_id"]]["kind"], "heuristic")
            self.assertIsNone(SOURCES[rule["source_id"]]["url"])
            self.assertEqual(rule["evidence_status"], "general_guide")
            self.assertTrue(rule["source_section"])
            self.assertIsNone(rule["source_page"])
            self.assertTrue(rule["evidence_note"])
            self.assertTrue(set(rule["symptoms"]).issubset({symptom["id"] for symptom in SYMPTOMS}))
            self.assertIn("rule_id", rule)
            self.assertIn("conditions", rule)
            self.assertIn("configuration", rule)
            self.assertEqual(rule["evidence_status"], "general_guide")
            self.assertEqual(rule["source_id"], "moto_rules")
            self.assertTrue(rule["systems"])
            self.assertTrue(rule["check"])
            self.assertTrue(rule["service_recommendation"])
            self.assertIn(rule["urgency"], {"normal", "check", "stop"})
            source = SOURCES[rule["source_id"]]
            self.assertTrue(source["title"])
            self.assertTrue(source["publisher"])
            self.assertTrue(source["section"])
            self.assertIn("note", source)
        self.assertEqual(
            sum(rule["evidence_status"] == "external_verified" for rule in RULES),
            0,
        )
        self.assertEqual(
            len({symptom_id for rule in RULES for symptom_id in rule["symptoms"]}),
            24,
        )

    def test_knowledge_search_and_category_filter(self):
        response = self.client.get("/pengetahuan?q=aki")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Aki dan kelistrikan", response.data)
        filtered = self.client.get("/pengetahuan?kategori=Kaki-kaki%20dan%20pengereman")
        self.assertEqual(filtered.status_code, 200)
        self.assertIn(b"Sistem pengereman", filtered.data)
        self.assertNotIn(b"CVT, kopling", filtered.data)

    def test_workshop_search_returns_real_provider_fields_only(self):
        provider_response = {
            "elements": [
                {
                    "type": "node",
                    "id": 101,
                    "lat": -6.2,
                    "lon": 106.8,
                    "tags": {
                        "shop": "motorcycle_repair",
                        "name": "Bengkel Contoh OSM",
                        "addr:street": "Jalan Contoh",
                        "phone": "+622100000",
                        "website": "javascript:alert(1)",
                    },
                },
                {
                    "type": "node",
                    "id": 102,
                    "lat": -6.21,
                    "lon": 106.81,
                    "tags": {"shop": "motorcycle_repair"},
                },
                {
                    "type": "way",
                    "id": 103,
                    "center": {"lat": -6.22, "lon": 106.82},
                    "tags": {
                        "motorcycle:repair": "yes",
                        "contact:phone": "++()",
                        "website": "https://example.com:99999",
                    },
                },
                {
                    "type": "node",
                    "id": 104,
                    "lat": -6.23,
                    "lon": 106.83,
                    "tags": {
                        "name": 123,
                        "addr:street": 456,
                        "phone": 789,
                        "website": "https://user:password@example.com",
                    },
                },
                {
                    "type": "way",
                    "id": 0,
                    "center": [],
                    "tags": {},
                },
            ]
        }
        with patch("motocheck.workshops.requests.post", return_value=FakeResponse(provider_response)) as mocked:
            response = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.2, "longitude": 106.8},
            )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["workshops"]
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["name"], "Bengkel Contoh OSM")
        self.assertEqual(result[0]["phone"], "+622100000")
        self.assertIsNone(result[0]["website"])
        self.assertIsNone(result[1]["name"])
        self.assertIsNone(result[1]["phone"])
        self.assertIsNone(result[2]["name"])
        self.assertIsNone(result[2]["phone"])
        self.assertIsNone(result[2]["website"])
        self.assertEqual(mocked.call_args.args[0], "https://overpass-api.de/api/interpreter")
        query = mocked.call_args.kwargs["data"]["data"]
        self.assertIn('shop"="motorcycle_repair"', query)
        self.assertIn('"motorcycle:repair"', query)
        self.assertTrue(mocked.call_args.kwargs["verify"])
        self.assertFalse(mocked.call_args.kwargs["allow_redirects"])

    def test_workshop_cache_does_not_repeat_nearby_query(self):
        response_data = {"elements": []}
        with patch("motocheck.workshops.requests.post", return_value=FakeResponse(response_data)) as mocked:
            first = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.2, "longitude": 106.8},
            )
            second = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.2001, "longitude": 106.8001},
            )
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.get_json()["cached"])
        self.assertTrue(second.get_json()["cached"])
        self.assertEqual(mocked.call_count, 1)

    def test_workshop_results_are_filtered_to_five_kilometers(self):
        response_data = {
            "elements": [
                {"type": "node", "id": 201, "lat": -6.23, "lon": 106.8, "tags": {"shop": "motorcycle_repair"}},
                {"type": "node", "id": 202, "lat": -6.26, "lon": 106.8, "tags": {"shop": "motorcycle_repair"}},
            ]
        }
        with patch("motocheck.workshops.requests.post", return_value=FakeResponse(response_data)):
            response = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.2, "longitude": 106.8},
            )
        self.assertEqual(response.status_code, 200)
        workshops = response.get_json()["workshops"]
        self.assertEqual([workshop["id"] for workshop in workshops], ["node/201"])

    def test_workshop_empty_error_and_invalid_coordinates(self):
        with patch("motocheck.workshops.requests.post", return_value=FakeResponse({"elements": []})):
            empty = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.2, "longitude": 106.8},
            )
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.get_json()["workshops"], [])

        clear_cache()
        invalid_json = FakeResponse({})
        invalid_json.json = lambda: (_ for _ in ()).throw(
            requests.exceptions.JSONDecodeError("bad response", "not-json", 0)
        )
        with patch("motocheck.workshops.requests.post", return_value=invalid_json):
            invalid = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.25, "longitude": 106.85},
            )
        self.assertEqual(invalid.status_code, 502)
        self.assertIn("tidak dapat dibaca", invalid.get_json()["error"])

        clear_cache()
        with patch(
            "motocheck.workshops.requests.post",
            side_effect=requests.exceptions.ConnectionError("offline"),
        ):
            failed = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.3, "longitude": 106.9},
            )
        self.assertEqual(failed.status_code, 502)
        self.assertIn("tidak dapat dihubungi", failed.get_json()["error"])
        for coordinates in (
            {"latitude": 91, "longitude": 0},
            {"latitude": float("nan"), "longitude": 0},
            {"latitude": True, "longitude": 0},
            {},
        ):
            response = self.client.post("/api/bengkel", json=coordinates)
            self.assertEqual(response.status_code, 400)

    def test_workshop_retries_transient_http_errors_with_verified_tls(self):
        with (
            patch(
                "motocheck.workshops.requests.post",
                side_effect=[
                    FakeResponse({"remark": "busy"}, status_code=503),
                    FakeResponse({"elements": []}),
                ],
            ) as mocked,
            patch("motocheck.workshops.time.sleep"),
        ):
            response = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.2, "longitude": 106.8},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(mocked.call_args.kwargs["timeout"], (3, 8))
        self.assertIs(mocked.call_args.kwargs["verify"], True)
        self.assertFalse(mocked.call_args.kwargs["allow_redirects"])
        self.assertIn("User-Agent", mocked.call_args.kwargs["headers"])

    def test_workshop_tls_verification_failure_is_not_retried_or_bypassed(self):
        error = requests.exceptions.SSLError("certificate verify failed")
        with patch("motocheck.workshops.requests.post", side_effect=error) as mocked:
            response = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.3, "longitude": 106.9},
            )
        self.assertEqual(response.status_code, 502)
        self.assertIn("gagal diverifikasi", response.get_json()["error"])
        self.assertEqual(mocked.call_count, 1)

    def test_workshop_does_not_retry_permanent_http_errors(self):
        with patch(
            "motocheck.workshops.requests.post",
            return_value=FakeResponse({"error": "not acceptable"}, status_code=406),
        ) as mocked:
            response = self.client.post(
                "/api/bengkel",
                json={"latitude": -6.3, "longitude": 106.9},
            )
        self.assertEqual(response.status_code, 502)
        self.assertIn("HTTP 406", response.get_json()["error"])
        self.assertEqual(mocked.call_count, 1)

    def test_finder_and_static_pages_load(self):
        self.assertEqual(self.client.get("/pengetahuan").status_code, 200)
        finder = self.client.get("/bengkel?urgensi=stop")
        self.assertEqual(finder.status_code, 200)
        self.assertIn(b"Jangan dikendarai", finder.data)
        script = self.client.get("/static/js/workshops.js")
        self.assertEqual(script.status_code, 200)
        script.close()


if __name__ == "__main__":
    unittest.main()
