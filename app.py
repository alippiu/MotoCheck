from flask import Flask, jsonify, render_template, request

from motocheck.catalog import (
    SYMPTOMS_BY_ID,
    build_vehicle,
    get_form_data,
)
from motocheck.diagnosis import (
    QUESTIONS,
    QUESTION_SYMPTOMS,
    RULES,
    diagnose,
    symptom_questions,
)
from motocheck.knowledge import categories as knowledge_categories
from motocheck.knowledge import search_topics
from motocheck.workshops import WorkshopSearchError, find_workshops

app = Flask(__name__)

SYMPTOM_EVIDENCE = {symptom_id: set() for symptom_id in SYMPTOMS_BY_ID}
for rule in RULES:
    for symptom_id in rule["symptoms"]:
        SYMPTOM_EVIDENCE[symptom_id].add(rule["evidence_status"])

SYMPTOM_SUPPORT = {}
for symptom_id, evidence_statuses in SYMPTOM_EVIDENCE.items():
    if "external_verified" in evidence_statuses:
        SYMPTOM_SUPPORT[symptom_id] = (
            "Ada aturan manual resmi untuk model/tahun tertentu"
        )
    elif "general_guide" in evidence_statuses:
        SYMPTOM_SUPPORT[symptom_id] = (
            "Panduan umum; belum tervalidasi untuk model ini"
        )
    else:
        SYMPTOM_SUPPORT[symptom_id] = "Belum ada analisis memadai"

EXTERNALLY_SUPPORTED_SYMPTOM_COUNT = sum(
    "external_verified" in statuses for statuses in SYMPTOM_EVIDENCE.values()
)
HEURISTIC_ONLY_SYMPTOM_COUNT = sum(
    "general_guide" in statuses and "external_verified" not in statuses
    for statuses in SYMPTOM_EVIDENCE.values()
)
UNSUPPORTED_SYMPTOM_COUNT = sum(
    not statuses for statuses in SYMPTOM_EVIDENCE.values()
)


def _render_home(error=None, status=200, selected=None):
    return (
        render_template(
            "index.html",
            **get_form_data(),
            error=error,
            selected=selected or {},
            question_options=QUESTIONS,
            question_symptoms=QUESTION_SYMPTOMS,
            symptom_support=SYMPTOM_SUPPORT,
            externally_supported_symptom_count=EXTERNALLY_SUPPORTED_SYMPTOM_COUNT,
            heuristic_only_symptom_count=HEURISTIC_ONLY_SYMPTOM_COUNT,
            unsupported_symptom_count=UNSUPPORTED_SYMPTOM_COUNT,
        ),
        status,
    )


@app.route("/")
def home():
    return _render_home()


@app.route("/periksa", methods=["POST"])
def periksa():
    form = request.form
    selected_ids = form.getlist("symptoms")
    primary_symptom_id = form.get("primary_symptom", "").strip()
    legacy_symptom = form.get("gejala", "").strip()
    legacy_motor = form.get("jenis_motor", "").strip()
    if not selected_ids and legacy_symptom:
        selected_ids = [legacy_symptom]

    if legacy_motor and not form.get("brand"):
        vehicle_form = {
            "brand": "other",
            "jenis_motor": legacy_motor,
            "category": "other",
            "fuel_system": "unknown",
            "cooling_system": "unknown",
            "final_drive": "unknown",
            "brakes": "unknown",
            "transmission": "unknown",
        }
    else:
        vehicle_form = form

    try:
        if not selected_ids:
            raise ValueError("Pilih minimal satu gejala yang dirasakan.")
        if len(selected_ids) > 10:
            raise ValueError("Pilih maksimal 10 gejala agar hasil tetap terarah.")
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("Gejala yang sama tidak dapat dipilih lebih dari sekali.")
        if primary_symptom_id and primary_symptom_id not in selected_ids:
            raise ValueError("Pilih gejala utama dari gejala yang dicentang.")
        if primary_symptom_id:
            selected_ids = [primary_symptom_id] + [
                symptom_id for symptom_id in selected_ids if symptom_id != primary_symptom_id
            ]

        vehicle = build_vehicle(vehicle_form)
        if not legacy_motor and form.get("jenis_motor"):
            raise ValueError("Jenis motor yang dikirim tidak valid.")

        relevant_questions = symptom_questions(set(selected_ids))
        answers = {}
        for question_id in QUESTIONS:
            value = form.get(question_id, "").strip()
            if not value:
                continue
            if question_id not in relevant_questions:
                raise ValueError("Pertanyaan lanjutan tidak sesuai dengan gejala yang dipilih.")
            if value not in QUESTIONS[question_id]["options"]:
                raise ValueError("Salah satu jawaban pemeriksaan tidak valid.")
            answers[question_id] = value

        result = diagnose(selected_ids, answers, vehicle)
    except ValueError as error:
        selected = form.to_dict()
        selected["symptoms"] = selected_ids
        return _render_home(str(error), 400, selected)

    selected_symptoms = [SYMPTOMS_BY_ID[symptom_id] for symptom_id in selected_ids]
    return render_template(
        "hasil.html",
        vehicle=vehicle,
        symptoms=selected_symptoms,
        result=result,
        workshop_query="Jangan Dikendarai" if result["urgency"] == "stop" else "",
    )


@app.route("/pengetahuan")
def knowledge():
    query = request.args.get("q", "")
    category = request.args.get("kategori", "")
    return render_template(
        "knowledge.html",
        topics=search_topics(query, category),
        categories=knowledge_categories(),
        query=query,
        selected_category=category,
    )


@app.route("/bengkel")
def workshop_page():
    return render_template(
        "workshops.html",
        urgency=request.args.get("urgensi", ""),
    )


@app.route("/api/bengkel", methods=["POST"])
def workshop_search():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Kirim koordinat lokasi setelah memberikan izin lokasi."), 400
    try:
        result = find_workshops(data.get("latitude"), data.get("longitude"))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except WorkshopSearchError as error:
        return jsonify(error=str(error)), 502

    return jsonify(
        workshops=result["workshops"],
        cached=result["cached"],
        radius_meters=5000,
        attribution="Data bengkel © OpenStreetMap contributors",
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
