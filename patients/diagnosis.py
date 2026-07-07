import re
from decimal import Decimal
from typing import Optional, Tuple

from django.utils import timezone

from .models import DiabetesAssessment, DiabetesDiagnosisSummary, LabResult, Patient


def _parse_numeric(value: str) -> Optional[Decimal]:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except Exception:
        return None


def _normalize_name(name: str) -> str:
    return (name or '').strip().lower()


def _latest_lab_by_aliases(patient: Patient, aliases: Tuple[str, ...]) -> Optional[LabResult]:
    labs = LabResult.objects.filter(patient=patient).order_by('-collected_at', '-created_at')
    for lab in labs:
        normalized = _normalize_name(lab.test_name)
        if any(alias in normalized for alias in aliases):
            return lab
    return None


def _has_confirmatory_repeat(patient: Patient, aliases: Tuple[str, ...], threshold: Decimal) -> bool:
    diabetic_dates = set()
    labs = LabResult.objects.filter(patient=patient).order_by('-collected_at', '-created_at')
    for lab in labs:
        normalized = _normalize_name(lab.test_name)
        if not any(alias in normalized for alias in aliases):
            continue
        value = _parse_numeric(lab.result_value)
        if value is None or value < threshold:
            continue
        date_value = timezone.localtime(lab.collected_at).date() if timezone.is_aware(lab.collected_at) else lab.collected_at.date()
        diabetic_dates.add(date_value)
        if len(diabetic_dates) >= 2:
            return True
    return False


def recompute_patient_diagnosis(patient: Patient) -> DiabetesDiagnosisSummary:
    latest_assessment = patient.diabetes_assessments.order_by('-assessed_at').first()

    fpg_lab = _latest_lab_by_aliases(patient, ('fasting plasma glucose', 'fasting glucose', 'fpg'))
    hba1c_lab = _latest_lab_by_aliases(patient, ('hba1c', 'hb a1c', 'a1c', 'glycated hemoglobin'))
    rpg_lab = _latest_lab_by_aliases(patient, ('random plasma glucose', 'random glucose', 'rpg'))

    fpg_value = _parse_numeric(fpg_lab.result_value) if fpg_lab else None
    hba1c_value = _parse_numeric(hba1c_lab.result_value) if hba1c_lab else None
    rpg_value = _parse_numeric(rpg_lab.result_value) if rpg_lab else None

    has_symptoms = None
    if latest_assessment is not None:
        has_symptoms = latest_assessment.classic_hyperglycemia_symptoms

    status = DiabetesDiagnosisSummary.STATUS_INDETERMINATE
    confirmation = DiabetesDiagnosisSummary.NOT_APPLICABLE
    reasons = []

    diabetic_fpg = fpg_value is not None and fpg_value >= Decimal('126')
    diabetic_hba1c = hba1c_value is not None and hba1c_value >= Decimal('6.5')
    diabetic_rpg = rpg_value is not None and rpg_value >= Decimal('200') and has_symptoms is True

    if diabetic_fpg:
        reasons.append('Fasting plasma glucose is in the diabetes range (>=126 mg/dL).')
    if diabetic_hba1c:
        reasons.append('HbA1c is in the diabetes range (>=6.5%).')
    if diabetic_rpg:
        reasons.append('Random plasma glucose is >=200 mg/dL with classic symptoms.')

    if diabetic_fpg or diabetic_hba1c or diabetic_rpg:
        status = DiabetesDiagnosisSummary.STATUS_DIABETES
        if diabetic_rpg:
            confirmation = DiabetesDiagnosisSummary.CONFIRMED
        elif sum([diabetic_fpg, diabetic_hba1c]) >= 2:
            confirmation = DiabetesDiagnosisSummary.CONFIRMED
        elif diabetic_fpg and _has_confirmatory_repeat(patient, ('fasting plasma glucose', 'fasting glucose', 'fpg'), Decimal('126')):
            confirmation = DiabetesDiagnosisSummary.CONFIRMED
        elif diabetic_hba1c and _has_confirmatory_repeat(patient, ('hba1c', 'hb a1c', 'a1c', 'glycated hemoglobin'), Decimal('6.5')):
            confirmation = DiabetesDiagnosisSummary.CONFIRMED
        else:
            confirmation = DiabetesDiagnosisSummary.PROVISIONAL
            reasons.append('In asymptomatic patients, confirm abnormal FPG/HbA1c on a separate day.')
    else:
        prediabetes_fpg = fpg_value is not None and Decimal('100') <= fpg_value <= Decimal('125')
        prediabetes_hba1c = hba1c_value is not None and Decimal('5.7') <= hba1c_value <= Decimal('6.4')

        if prediabetes_fpg or prediabetes_hba1c:
            status = DiabetesDiagnosisSummary.STATUS_PREDIABETES
            confirmation = DiabetesDiagnosisSummary.NOT_APPLICABLE
            if prediabetes_fpg:
                reasons.append('Fasting plasma glucose is in the prediabetes range (100-125 mg/dL).')
            if prediabetes_hba1c:
                reasons.append('HbA1c is in the prediabetes range (5.7-6.4%).')
        elif fpg_value is not None or hba1c_value is not None or rpg_value is not None:
            status = DiabetesDiagnosisSummary.STATUS_NORMAL
            confirmation = DiabetesDiagnosisSummary.NOT_APPLICABLE
            reasons.append('Available FPG and HbA1c values are below diabetes and prediabetes thresholds.')
        else:
            status = DiabetesDiagnosisSummary.STATUS_INDETERMINATE
            confirmation = DiabetesDiagnosisSummary.NOT_APPLICABLE
            reasons.append('No usable FPG, HbA1c, or random glucose lab values were found.')

    summary, _created = DiabetesDiagnosisSummary.objects.update_or_create(
        patient=patient,
        defaults={
            'status': status,
            'confirmation_status': confirmation,
            'reason': ' '.join(reasons),
            'fasting_plasma_glucose': fpg_value,
            'hba1c': hba1c_value,
            'random_plasma_glucose': rpg_value,
            'has_classic_symptoms': has_symptoms,
            'source_assessment': latest_assessment,
            'source_fpg_lab': fpg_lab,
            'source_hba1c_lab': hba1c_lab,
            'source_rpg_lab': rpg_lab,
            'evaluated_at': timezone.now(),
        },
    )
    return summary
