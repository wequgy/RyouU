"""Synchronous ID-details OCR gate check.

Extracts text via RapidOCR (onnxruntime) from the uploaded ID image and compares
against user-entered verification details:
1. Name: Every token of the entered name must fuzzy-match a token on the ID (rapidfuzz >= 80).
2. DOB: Parse all dates found on the ID (dateparser, day-first) and require one to match entered dob.
3. ID Last 4: Some digit run on the ID (merging space-separated groups) must end with entered last 4.
4. Input requirements: Name AND at least one of DOB / id_last4 must be supplied.
5. Quality: Unreadable ID (< 2 text boxes or low confidence) fails with a clear message:
   "Unreadable ID: retake a clearer photo".
"""
import io
import re
from typing import Tuple, Dict, Any, Optional
import numpy as np

from ..models import CheckContext, CheckResult
from .base import register


_OCR = None


def _get_ocr():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    return _OCR


def extract_id_text_and_boxes(image_bytes: bytes):
    """Run RapidOCR on image bytes and return list of (text, confidence) and merged raw text."""
    ocr = _get_ocr()
    result, _ = ocr(image_bytes)
    if not result:
        return [], ""
    boxes = []
    texts = []
    for line in result:
        # line structure: [bbox, text, score]
        if len(line) >= 3:
            text = str(line[1]).strip()
            score = float(line[2])
            if text:
                boxes.append((text, score))
                texts.append(text)
    return boxes, " ".join(texts)


def verify_id_details(image_bytes: bytes, expected: dict) -> Tuple[bool, str, Dict[str, Any]]:
    """Synchronously verify ID image text against expected details.
    
    Returns:
        (passed: bool, reason: str, details: dict)
    """
    name = (expected.get("name") or "").strip()
    dob = (expected.get("dob") or "").strip()
    id_last4 = (expected.get("id_last4") or "").strip()

    # Rule 4: Require name AND at least one of dob / id_last4
    if not name or (not dob and not id_last4):
        return False, "Verification requires name and at least one of date of birth or ID last 4 digits", {}

    try:
        boxes, full_text = extract_id_text_and_boxes(image_bytes)
    except Exception as e:
        return False, f"OCR processing failed: {e}", {}

    # Rule 5: Unreadable ID (too few text boxes / low OCR confidence)
    if len(boxes) < 2:
        return False, "Unreadable ID: retake a clearer photo", {"box_count": len(boxes)}

    confidences = [b[1] for b in boxes]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    if avg_conf < 0.40 and len(boxes) < 4:
        return False, "Unreadable ID: retake a clearer photo", {"avg_confidence": avg_conf, "box_count": len(boxes)}

    from rapidfuzz import fuzz
    from ..textutil import parse_date

    mismatches = []
    match_details = {"avg_confidence": round(avg_conf, 3), "box_count": len(boxes)}

    # 1. Name check: every token of entered name must fuzzy-match a token on the ID (rapidfuzz >= 80)
    name_tokens = [t.lower() for t in re.split(r"[\s,.-]+", name) if len(t) >= 2]
    id_tokens = [t.lower() for b in boxes for t in re.split(r"[\s,.-]+", b[0]) if t]

    name_matched = True
    token_matches = {}
    for nt in name_tokens:
        best_ratio = max([fuzz.ratio(nt, it) for it in id_tokens], default=0)
        token_matches[nt] = best_ratio
        if best_ratio < 80:
            best_partial = max([fuzz.partial_ratio(nt, it) for it in id_tokens], default=0)
            if best_partial < 85:
                name_matched = False

    match_details["name_token_scores"] = token_matches
    if not name_matched:
        mismatches.append("name")

    # 2. DOB check: parse all dates on the ID (day-first) and require one to equal entered dob
    if dob:
        entered_date = parse_date(dob)
        if not entered_date:
            mismatches.append("dob")
            match_details["dob_error"] = "Invalid format for entered DOB"
        else:
            # Candidate date patterns from ID text
            date_matches = re.findall(
                r"\b\d{1,2}[-/\.\s]\d{1,2}[-/\.\s]\d{2,4}\b|\b\d{4}[-/\.\s]\d{1,2}[-/\.\s]\d{1,2}\b|\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b",
                full_text
            )
            parsed_id_dates = []
            for dm in date_matches:
                dt = parse_date(dm)
                if dt:
                    parsed_id_dates.append(dt)

            dob_found = any(dt == entered_date for dt in parsed_id_dates)
            match_details["id_dates_found"] = [str(d) for d in parsed_id_dates]
            match_details["entered_dob_parsed"] = str(entered_date)
            if not dob_found:
                mismatches.append("dob")

    # 3. id_last4 check: some digit run on ID (merge space-separated groups) ends with entered last 4
    if id_last4:
        clean_target = "".join(c for c in id_last4 if c.isdigit())[-4:]
        merged_digits = re.sub(r"(?<=\d)\s+(?=\d)", "", full_text)
        digit_runs = re.findall(r"\d{4,}", merged_digits)
        last4_found = any(run.endswith(clean_target) for run in digit_runs)
        match_details["target_last4"] = clean_target
        match_details["digit_runs_found"] = digit_runs
        if not last4_found:
            mismatches.append("id_last4")

    if mismatches:
        fields_str = ", ".join(mismatches)
        return False, f"ID details mismatch for field(s): {fields_str}", match_details

    return True, "ID details match successfully", match_details


@register("id_details")
def id_details(ctx: CheckContext) -> CheckResult:
    """Policy-level check evaluation for id_details."""
    if not ctx.settings.enforce_gates:
        return CheckResult("id_details", "pass", 1.0, 1.0, "Gates not enforced (test mode)", {})

    gates = ctx.data.get("gates", {})
    gate_res = gates.get("id_image")
    if not gate_res:
        id_path = ctx.files.get("id_image")
        if not id_path:
            return CheckResult.skipped("id_details", "No ID image provided")
        try:
            with open(id_path, "rb") as f:
                blob = f.read()
            expected = (ctx.data.get("expected") or {})
            ok, reason, details = verify_id_details(blob, expected)
            status = "pass" if ok else "fail"
            return CheckResult("id_details", status, 1.0 if ok else 0.0, 0.9, reason, details)
        except Exception as e:
            return CheckResult.uncertain("id_details", f"ID details check failed: {e}")

    passed = gate_res.get("passed", False)
    status = "pass" if passed else "fail"
    return CheckResult(
        "id_details",
        status,
        1.0 if passed else 0.0,
        0.9,
        gate_res.get("reason", "ID details verified"),
        gate_res.get("ocr_details", {})
    )
