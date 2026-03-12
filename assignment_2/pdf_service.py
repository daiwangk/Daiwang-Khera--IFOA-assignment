from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

import fitz  # PyMuPDF

from assignment_2.certificate_coordinates import certificate_coordinates

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATED_CERTS_DIR = PROJECT_ROOT / "generated_certs"


def _format_date_upper(value: date | datetime) -> str:
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d %B %Y").upper()


def _safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_\- ]+", "", value).strip()
    return re.sub(r"\s+", "_", value) or "certificate"


def _resolve_template_path(template_value: str) -> Path:
    candidate = (PROJECT_ROOT / template_value).resolve()
    if candidate.exists():
        return candidate

    fallback = (Path(__file__).resolve().parent / "templates" / Path(template_value).name).resolve()
    if fallback.exists():
        return fallback

    raise ValueError(f"Template not found: {template_value}")


def generate_certificate(record, selected_modules: list | None = None) -> str:
    training_type = str(record.type_of_training)
    config = certificate_coordinates.get(training_type)
    if not config:
        raise ValueError(f"Unsupported training type: {training_type}")

    training_date_value = record.training_date
    if isinstance(training_date_value, datetime):
        training_date_value = training_date_value.date()
    if not isinstance(training_date_value, date):
        raise ValueError("record.training_date must be a date or datetime value")

    training_date_text = _format_date_upper(training_date_value)
    validity_date_text = _format_date_upper(training_date_value + timedelta(days=365))

    template_path = _resolve_template_path(str(config["template"]))

    data_map = {
        "participant_name": str(record.participant_name),
        "training_date": training_date_text,
        "company": str(record.company),
        "department": str(record.department),
        "validity_date": validity_date_text,
        "modules": " / ".join(selected_modules) if selected_modules else "",
    }

    doc = fitz.open(str(template_path))
    try:
        page = doc[0]
        fields = config.get("fields", {})

        for key, field_meta in fields.items():
            text_value = data_map.get(key)
            if text_value is None:
                text_value = str(getattr(record, key, ""))

            if key == "modules" and not selected_modules:
                continue
            if not text_value:
                continue

            x = float(field_meta["x"])
            y = float(field_meta["y"])
            fontsize = float(field_meta["fontsize"])
            page.insert_text(fitz.Point(x, y), text_value, fontsize=fontsize)

        GENERATED_CERTS_DIR.mkdir(parents=True, exist_ok=True)
        participant_name = _safe_filename(str(record.participant_name))
        training_name = _safe_filename(training_type)
        output_path = (GENERATED_CERTS_DIR / f"{participant_name}_{training_name}.pdf").resolve()

        doc.save(str(output_path))
    finally:
        doc.close()

    return str(output_path)
