import json
from pathlib import Path
from urllib.parse import urlparse

from motocheck.catalog import MODELS_BY_ID, SOURCES, SYMPTOMS_BY_ID


RULES_PATH = Path(__file__).parent / "data" / "rules.json"
with RULES_PATH.open(encoding="utf-8") as rules_file:
    RULES = json.load(rules_file)

EVIDENCE_STATUSES = {"external_verified", "general_guide"}


def validate_rule_evidence(rules, sources):
    seen_rule_ids = set()
    valid_symptoms = set(SYMPTOMS_BY_ID)
    known_model_years = {
        (model["id"], str(variant["year"]))
        for model in MODELS_BY_ID.values()
        for variant in model["variants"]
        if variant.get("year") is not None
    }
    for rule in rules:
        rule_id = rule.get("rule_id")
        if not rule_id or rule_id in seen_rule_ids:
            raise ValueError("ID aturan diagnosis kosong atau duplikat.")
        seen_rule_ids.add(rule_id)
        symptoms = rule.get("symptoms")
        if not isinstance(symptoms, list) or not set(symptoms).issubset(valid_symptoms):
            raise ValueError(f"Gejala pada aturan {rule_id} tidak tersedia.")

        evidence_status = rule.get("evidence_status")
        if evidence_status not in EVIDENCE_STATUSES:
            raise ValueError(f"Status bukti aturan {rule_id} tidak dikenali.")
        source = sources.get(rule.get("source_id"))
        if not source:
            raise ValueError(f"Sumber aturan {rule_id} tidak ditemukan.")
        if evidence_status == "general_guide":
            if source.get("kind") != "heuristic" or source.get("url") is not None:
                raise ValueError(
                    f"Aturan umum {rule_id} tidak boleh tampil sebagai dokumen eksternal."
                )
            continue

        coverage = source.get("coverage")
        verified_scope = rule.get("verified_scope")
        claims = source.get("verified_rule_claims")
        source_claim = claims.get(rule_id) if isinstance(claims, dict) else None
        valid_coverage = (
            isinstance(coverage, list)
            and all(
                isinstance(item, dict)
                and (item.get("catalog_model_id"), str(item.get("year")))
                in known_model_years
                for item in coverage
            )
        )
        valid_scope = (
            isinstance(verified_scope, list)
            and all(
                isinstance(item, dict)
                and (item.get("catalog_model_id"), str(item.get("year")))
                in known_model_years
                for item in verified_scope
            )
        )
        coverage_pairs = (
            {
                (item["catalog_model_id"], str(item["year"]))
                for item in coverage
                if isinstance(item, dict)
            }
            if valid_coverage
            else set()
        )
        scope_pairs = (
            {
                (item["catalog_model_id"], str(item["year"]))
                for item in verified_scope
                if isinstance(item, dict)
            }
            if valid_scope
            else set()
        )
        parsed_url = urlparse(source.get("url", "")) if isinstance(source.get("url"), str) else None
        if (
            source.get("kind") != "manufacturer_owner_manual"
            or source.get("content_reviewed") is not True
            or not source.get("title")
            or not source.get("publisher")
            or not parsed_url
            or parsed_url.scheme != "https"
            or not parsed_url.hostname
            or not (rule.get("source_section") or rule.get("source_page"))
            or not valid_coverage
            or not valid_scope
            or not scope_pairs
            or not scope_pairs.issubset(coverage_pairs)
            or not rule.get("evidence_claim")
            or not rule.get("evidence_note")
            or not isinstance(source_claim, str)
            or not source_claim.strip()
        ):
            raise ValueError(
                f"Aturan {rule_id} belum memiliki bukti manual dan cakupan model/tahun yang lengkap."
            )


validate_rule_evidence(RULES, SOURCES)

QUESTIONS = {
    "when": {
        "label": "Kapan gejala paling sering muncul?",
        "options": {
            "cold": "Saat mesin dingin",
            "hot": "Saat mesin panas",
            "any": "Tidak bergantung kondisi mesin",
        },
    },
    "situation": {
        "label": "Dalam kondisi apa keluhan muncul?",
        "options": {
            "idle": "Saat langsam",
            "acceleration": "Saat akselerasi",
            "speed": "Saat motor melaju",
            "braking": "Saat mengerem",
            "any": "Kapan saja",
        },
    },
    "starter": {
        "label": "Bagaimana respons starter?",
        "options": {
            "normal": "Berputar normal",
            "weak": "Berputar lemah/lambat",
            "silent": "Tidak ada respons",
            "kick_only": "Hanya bisa dengan engkol",
            "unknown": "Tidak tahu / tidak relevan",
        },
    },
    "indicator": {
        "label": "Apakah ada indikator yang menyala atau perangkat listrik melemah?",
        "options": {
            "none": "Tidak ada",
            "weak_battery": "Lampu/klakson ikut melemah",
            "injection": "Indikator injeksi menyala",
            "temperature": "Indikator suhu menyala",
            "unknown": "Tidak tahu / tidak relevan",
        },
    },
    "sound": {
        "label": "Apakah ada bunyi tertentu yang bisa dijelaskan?",
        "options": {
            "none": "Tidak ada bunyi khusus",
            "rattle": "Bunyi bergetar / berderak",
            "knocking": "Bunyi ketukan",
            "scraping": "Bunyi gesekan",
            "other": "Bunyi lain",
            "unknown": "Tidak tahu",
        },
    },
}

QUESTION_SYMPTOMS = {question_id: set() for question_id in QUESTIONS}
for rule in RULES:
    for question_id in rule["conditions"]:
        if question_id in QUESTION_SYMPTOMS:
            QUESTION_SYMPTOMS[question_id].update(rule["symptoms"])

SAFETY_SYMPTOMS = {
    "mesin_panas": "stop",
    "kebocoran_pendingin": "stop",
    "kebocoran_oli": "stop",
    "rem_kurang_pakem": "stop",
    "rem_bergetar": "stop",
    "gangguan_kemudi": "stop",
    "setang_bergetar": "stop",
    "ban_aus_tidak_merata": "stop",
    "kebocoran_bahan_bakar": "stop",
}

URGENCY_LABELS = {
    "normal": "Pemeriksaan rutin",
    "check": "Perlu Diperiksa",
    "stop": "Jangan Dikendarai",
}


def symptom_questions(selected_symptoms):
    question_ids = {
        question_id
        for question_id, relevant_symptoms in QUESTION_SYMPTOMS.items()
        if selected_symptoms & relevant_symptoms
    }
    return {question_id: QUESTIONS[question_id] for question_id in QUESTIONS if question_id in question_ids}


def _rule_matches(rule, selected_symptoms, vehicle):
    matched_symptoms = selected_symptoms.intersection(rule["symptoms"])
    if not matched_symptoms:
        return None

    if rule["evidence_status"] == "external_verified":
        verified_pair = (
            vehicle.get("catalog_model_id"),
            str(vehicle.get("year")),
        )
        if not vehicle.get("year_verified") or verified_pair not in {
            (item["catalog_model_id"], str(item["year"]))
            for item in rule["verified_scope"]
        }:
            return None

    config = rule.get("configuration", {})
    vehicle_configuration = vehicle["configuration_ids"]
    for field, allowed in config.items():
        if "any" not in allowed and vehicle_configuration.get(field) not in allowed:
            return None

    return matched_symptoms


def diagnose(selected_symptom_ids, answers, vehicle):
    selected_ids = list(selected_symptom_ids)
    selected_symptoms = set(selected_ids)
    if not selected_ids:
        raise ValueError("Pilih minimal satu gejala.")
    if not selected_symptoms.issubset(SYMPTOMS_BY_ID):
        raise ValueError("Ada gejala yang tidak tersedia.")
    if any(
        question_id not in QUESTIONS
        or answer not in QUESTIONS[question_id]["options"]
        for question_id, answer in answers.items()
    ):
        raise ValueError("Ada jawaban pemeriksaan yang tidak tersedia.")

    candidates = []
    for order, rule in enumerate(RULES):
        matched_symptoms = _rule_matches(rule, selected_symptoms, vehicle)
        if not matched_symptoms:
            continue
        rank = len(matched_symptoms) * 3
        match_explanation = [
            f"Gejala yang dipilih sesuai aturan: {SYMPTOMS_BY_ID[symptom_id]['name']}."
            for symptom_id in selected_ids
            if symptom_id in matched_symptoms
        ]
        question_effects = []
        unanswered_conditions = []
        for question_id, expected in rule["conditions"].items():
            answer = answers.get(question_id)
            if answer is None:
                unanswered_conditions.append(QUESTIONS[question_id]["label"])
                continue
            answer_label = QUESTIONS[question_id]["options"][answer]
            if answer in expected:
                rank += 2
                effect = (
                    "Mendukung kecocokan dengan manual resmi"
                    if rule["evidence_status"] == "external_verified"
                    else "Mendukung kecocokan aturan umum"
                )
                match_explanation.append(
                    f"Jawaban “{answer_label}” selaras dengan kondisi aturan."
                )
            else:
                rank -= 2
                effect = "Tidak selaras; dugaan ini menjadi lebih lemah"
                match_explanation.append(
                    f"Jawaban “{answer_label}” tidak selaras dengan kondisi aturan."
                )
            question_effects.append(
                {
                    "question": QUESTIONS[question_id]["label"],
                    "answer": answer_label,
                    "effect": effect,
                }
            )

        for field, allowed in rule.get("configuration", {}).items():
            if "any" in allowed:
                continue
            if vehicle["configuration_ids"].get(field) in allowed:
                config_label = vehicle["configuration"].get(field, "Belum dikonfirmasi")
                provenance = vehicle.get("configuration_provenance", {}).get(
                    field, "Belum diketahui"
                )
                match_explanation.append(
                    f"Konfigurasi {field.replace('_', ' ')}: {config_label} ({provenance.lower()})."
                )

        evidence_status = rule["evidence_status"]
        source = {
            **SOURCES[rule["source_id"]],
            "section": rule.get("source_section"),
            "page": rule.get("source_page"),
        }
        source_scope = (
            ", ".join(
                f"{MODELS_BY_ID[item['catalog_model_id']]['name']} (tahun {item['year']})"
                for item in rule["verified_scope"]
            )
            if evidence_status == "external_verified"
            else source.get("model_year_scope", "Tidak spesifik model atau tahun.")
        )
        candidates.append(
            {
                "rule_id": rule["rule_id"],
                "candidate": rule["candidate"],
                "reason": rule["reason"],
                "match_explanation": match_explanation,
                "question_effects": question_effects,
                "unanswered_conditions": unanswered_conditions,
                "systems": rule["systems"],
                "check": rule["check"],
                "urgency": rule["urgency"],
                "source": source,
                "evidence_status": evidence_status,
                "evidence_status_label": (
                    "Berdasarkan manual resmi untuk model/tahun yang tercantum"
                    if evidence_status == "external_verified"
                    else "Panduan umum — belum tervalidasi untuk model ini"
                ),
                "source_scope": source_scope,
                "evidence_note": rule.get(
                    "evidence_note",
                    "Belum ada dokumen troubleshooting yang memvalidasi aturan ini untuk kendaraan yang dipilih.",
                ),
                "service_recommendation": rule.get(
                    "service_recommendation",
                    "Minta pemeriksaan langsung di bengkel sepeda motor umum; MotoCheck tidak memverifikasi keahlian khusus bengkel.",
                ),
                "symptoms": [
                    SYMPTOMS_BY_ID[symptom_id]["name"]
                    for symptom_id in selected_ids
                    if symptom_id in matched_symptoms
                ],
                "_sort": (-rank, order),
            }
        )
    candidates.sort(key=lambda candidate: candidate["_sort"])
    for candidate in candidates:
        candidate.pop("_sort")

    unsupported = sorted(
        (SYMPTOMS_BY_ID[symptom_id]["name"] for symptom_id in selected_symptoms),
        key=str.casefold,
    )
    rule_supported_symptoms = {
        symptom_id
        for rule in RULES
        for symptom_id in selected_symptoms.intersection(rule["symptoms"])
        if _rule_matches(rule, selected_symptoms, vehicle)
    }
    unsupported_ids = selected_symptoms - rule_supported_symptoms
    unsupported = [
        SYMPTOMS_BY_ID[symptom_id]["name"]
        for symptom_id in sorted(unsupported_ids)
    ]

    urgency = "check"
    if any(SAFETY_SYMPTOMS.get(symptom_id) == "stop" for symptom_id in selected_symptoms):
        urgency = "stop"
    elif any(candidate["urgency"] == "stop" for candidate in candidates):
        urgency = "stop"
    elif any(candidate["urgency"] == "check" for candidate in candidates):
        urgency = "check"

    answered_questions = [
        {
            "question": QUESTIONS[question_id]["label"],
            "answer": QUESTIONS[question_id]["options"][value],
        }
        for question_id, value in answers.items()
        if question_id in QUESTIONS and value in QUESTIONS[question_id]["options"]
    ]
    primary_symptom = SYMPTOMS_BY_ID[selected_ids[0]]["name"]
    additional_symptoms = [
        SYMPTOMS_BY_ID[symptom_id]["name"] for symptom_id in selected_ids[1:]
    ]
    return {
        "candidates": candidates,
        "unsupported_symptoms": unsupported,
        "primary_symptom": primary_symptom,
        "additional_symptoms": additional_symptoms,
        "urgency": urgency,
        "urgency_label": URGENCY_LABELS[urgency],
        "answers": {
            question_id: QUESTIONS[question_id]["options"][value]
            for question_id, value in answers.items()
            if question_id in QUESTIONS and value in QUESTIONS[question_id]["options"]
        },
        "answered_questions": answered_questions,
        "sources": [SOURCES["moto_rules"]],
        "external_evidence_count": sum(
            1
            for candidate in candidates
            if candidate["evidence_status"] == "external_verified"
        ),
        "message": (
            "Bukti belum cukup untuk menyusun kandidat penyebab."
            if not candidates
            else "Ada kandidat yang didukung manual resmi sesuai model dan tahun; kandidat tetap bukan diagnosis pasti."
            if any(
                candidate["evidence_status"] == "external_verified"
                for candidate in candidates
            )
            else "Bukti teknis belum cukup untuk memastikan penyebab. Kandidat yang muncul hanya panduan umum untuk menentukan area pemeriksaan awal."
        ),
    }
