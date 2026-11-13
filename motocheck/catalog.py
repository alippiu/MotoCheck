import json
import re
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"


def _read_json(filename):
    with (DATA_DIR / filename).open(encoding="utf-8") as data_file:
        return json.load(data_file)


CATALOG = _read_json("vehicles.json")
SOURCES = _read_json("sources.json")
SYMPTOMS = _read_json("symptoms.json")
SYMPTOMS_BY_ID = {symptom["id"]: symptom for symptom in SYMPTOMS}
MODELS_BY_ID = {model["id"]: model for model in CATALOG["models"]}

MOTOR_TYPES = {
    "matic": "Matic",
    "manual": "Manual",
}

CONFIGURATION_OPTIONS = {
    "category": CATALOG["categories"],
    "transmission": CATALOG["transmissions"],
    "fuel_system": CATALOG["fuel_systems"],
    "cooling_system": CATALOG["cooling_systems"],
    "final_drive": CATALOG["final_drives"],
    "brakes": CATALOG["brakes"],
    "front_brake": CATALOG["brake_types"],
    "rear_brake": CATALOG["brake_types"],
}


def _option_values(options):
    return {option["id"] for option in options}


def get_form_data():
    catalog = {
        **CATALOG,
        "models": [
            {
                **model,
                "variants": [
                    {
                        **variant,
                        "configuration": {
                            **model.get("configuration", {}),
                            **variant.get("configuration", {}),
                        },
                    }
                    for variant in model["variants"]
                ],
            }
            for model in CATALOG["models"]
        ],
    }
    return {
        "catalog": catalog,
        "model_sources": [
            {**SOURCES[model["source_id"]], "facts": model["verified_facts"]}
            for model in CATALOG["models"]
        ],
        "symptoms": SYMPTOMS,
        "legacy_motor_types": MOTOR_TYPES,
    }


def build_vehicle(form):
    brand = form.get("brand", "").strip()
    brand_names = {item["id"]: item["name"] for item in CATALOG["brands"]}
    if brand not in brand_names:
        raise ValueError("Pilih merek dari daftar atau pilih Merek lain / tidak tahu.")

    model_id = form.get("model", "").strip()
    model_custom = form.get("model_custom", "").strip()
    variant_id = form.get("variant", "").strip()
    variant_custom = form.get("variant_custom", "").strip()
    model_record = MODELS_BY_ID.get(model_id)
    model_source = None
    verified_configuration = {}
    variant_verified = False
    verified_year = None
    if model_record:
        if model_record["brand_id"] != brand:
            raise ValueError("Model yang dipilih tidak sesuai dengan merek motor.")
        variants = {variant["id"]: variant for variant in model_record["variants"]}
        variant_record = variants.get(variant_id)
        if variant_id not in {"", "other"} and not variant_record:
            raise ValueError("Pilih varian yang tersedia atau tandai sebagai tidak diketahui.")
        model = model_record["name"]
        variant_verified = variant_record is not None
        if variant_record:
            verified_configuration = dict(model_record.get("configuration", {}))
            verified_configuration.update(variant_record.get("configuration", {}))
            verified_year = variant_record.get("year")
            if variant_record.get("source_id"):
                model_source = SOURCES[variant_record["source_id"]]
        variant = (
            variant_record["name"]
            if variant_record
            else variant_custom or "Tidak diketahui"
        )
        if model_source is None:
            model_source = SOURCES[model_record["source_id"]]
    else:
        model = model_custom if model_id == "other" else model_id or model_custom
        variant = variant_custom if variant_id == "other" else variant_id or variant_custom

    if len(model) > 80 or len(variant) > 80:
        raise ValueError("Nama model dan varian maksimal 80 karakter.")

    year_text = form.get("year", "").strip()
    if verified_year:
        if year_text and year_text != str(verified_year):
            raise ValueError("Tahun pada varian resmi tidak sesuai dengan tahun yang diisi.")
        year_text = str(verified_year)
    if year_text and (not re.fullmatch(r"\d{4}", year_text) or not 1950 <= int(year_text) <= 2100):
        raise ValueError("Tahun motor harus berupa angka 4 digit yang valid.")

    configuration = {}
    user_configuration = {}
    configuration_provenance = {}
    for field, options in CONFIGURATION_OPTIONS.items():
        default = "other" if field == "category" else "unknown"
        value = form.get(field, default).strip() or default
        if value not in _option_values(options):
            raise ValueError("Pilih konfigurasi motor dari pilihan yang tersedia.")
        user_configuration[field] = value
        if field in verified_configuration:
            value = verified_configuration[field]
        configuration[field] = value
        configuration_provenance[field] = (
            "Tercantum pada sumber resmi"
            if field in verified_configuration
            else "Isian pengguna"
            if value != "unknown" and value != "other"
            else "Belum diketahui"
        )

    legacy_type = form.get("jenis_motor", "").strip()
    if legacy_type and legacy_type not in MOTOR_TYPES:
        raise ValueError("Jenis motor yang dikirim tidak valid.")
    if legacy_type and configuration["transmission"] == "unknown":
        configuration["transmission"] = "cvt" if legacy_type == "matic" else "manual_clutch"
        configuration_provenance["transmission"] = (
            "Diturunkan dari jenis motor lama yang diisi pengguna"
        )

    option_names = {
        field: {item["id"]: item["name"] for item in options}
        for field, options in CONFIGURATION_OPTIONS.items()
    }
    return {
        "brand_id": brand,
        "catalog_model_id": model_record["id"] if model_record else None,
        "catalog_variant_id": variant_record["id"] if model_record and variant_record else None,
        "brand": brand_names[brand],
        "model": model or "Tidak diketahui",
        "variant": variant or "Tidak diketahui",
        "year": year_text or "Tidak diketahui",
        "year_verified": verified_year is not None,
        "year_provenance": (
            "Tercantum pada portal resmi"
            if verified_year is not None
            else "Diisi pengguna; belum diverifikasi"
            if year_text
            else "Belum diketahui"
        ),
        "category": option_names["category"][configuration["category"]],
        "category_id": configuration["category"],
        "configuration": {
            field: option_names[field][value]
            for field, value in configuration.items()
        },
        "user_configuration": {
            field: option_names[field][value]
            for field, value in user_configuration.items()
            if value in option_names[field]
        },
        "configuration_provenance": configuration_provenance,
        "configuration_ids": configuration,
        "verified_configuration": verified_configuration,
        "model_source": model_source,
        "variant_verified": variant_verified,
        "legacy_type": legacy_type,
        "verification": (
            (
                (
                    "Model dan varian tercantum pada halaman produk resmi. "
                    "Hanya konfigurasi yang disebut pada sumber yang digunakan."
                    if model_source["kind"] == "manufacturer_product_page"
                    else "Model, varian, atau tahun tercantum pada portal resmi. Isi dokumen manual belum dipakai untuk memverifikasi konfigurasi."
                )
                if variant_verified
                else "Model tercantum pada sumber resmi, tetapi varian dan konfigurasinya belum terverifikasi."
            )
            if model_source
            else "Model, varian, tahun, dan konfigurasi mengikuti keterangan pengguna dan belum diverifikasi melalui dokumen pabrikan."
        ),
    }
