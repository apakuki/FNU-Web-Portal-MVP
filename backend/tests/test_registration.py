"""Unit tests for registration helpers: prereq validator, clash detector, GPA, fee calculator."""

import pytest

from src.backend.api.registration import (
    GPA_POINTS,
    calculate_gpa,
    calculate_registration_fees,
    calculate_semester_gpas,
    check_prerequisites,
    detect_clashes,
)
from src.backend.banner.types import Campus, CompletedCourse, FeeItem, Offering, Semester

# ---------- Helpers to build test fixtures ----------

def _completed(
    course_code: str, grade: str, credits: int = 15, year: int = 2025, semester: str = "S1"
) -> CompletedCourse:
    return CompletedCourse(
        course_code=course_code,
        course_name=f"{course_code} Name",
        grade=grade,
        credits=credits,
        semester=Semester(semester),
        year=year,
    )


def _offering(
    id: str,
    course_code: str,
    day: str,
    start: str,
    end: str,
) -> Offering:
    return Offering(
        id=id,
        course_code=course_code,
        semester=Semester.S1,
        year=2026,
        campus=Campus.NASINU,
        lecturer_name="Dr. Test",
        day_of_week=day,
        start_time=start,
        end_time=end,
        room="A101",
        capacity=30,
        enrolled=10,
    )


# ---------- check_prerequisites ----------

def test_prereqs_empty_always_met():
    met, issues = check_prerequisites("ACC201", [], [])
    assert met is True
    assert issues == []


def test_prereqs_course_not_completed():
    met, issues = check_prerequisites("ACC201", [{"course_code": "ACC101", "min_grade": None}], [])
    assert met is False
    assert any("ACC101" in i for i in issues)


def test_prereqs_course_completed_no_min_grade():
    completed = [_completed("ACC101", "C")]
    met, issues = check_prerequisites(
        "ACC201", [{"course_code": "ACC101", "min_grade": None}], completed
    )
    assert met is True
    assert issues == []


def test_prereqs_grade_below_minimum():
    completed = [_completed("ACC101", "C")]
    met, issues = check_prerequisites(
        "ACC201", [{"course_code": "ACC101", "min_grade": "B"}], completed
    )
    assert met is False
    assert any("below required" in i for i in issues)


def test_prereqs_grade_meets_minimum():
    completed = [_completed("ACC101", "A")]
    met, issues = check_prerequisites(
        "ACC201", [{"course_code": "ACC101", "min_grade": "B"}], completed
    )
    assert met is True
    assert issues == []


def test_prereqs_multiple_one_missing():
    completed = [_completed("ACC101", "A")]
    prereqs = [
        {"course_code": "ACC101", "min_grade": None},
        {"course_code": "MGT101", "min_grade": None},
    ]
    met, issues = check_prerequisites("ACC301", prereqs, completed)
    assert met is False
    assert any("MGT101" in i for i in issues)


def test_prereqs_multiple_all_met():
    completed = [_completed("ACC101", "A"), _completed("MGT101", "B")]
    prereqs = [
        {"course_code": "ACC101", "min_grade": None},
        {"course_code": "MGT101", "min_grade": None},
    ]
    met, issues = check_prerequisites("ACC301", prereqs, completed)
    assert met is True
    assert issues == []


# ---------- detect_clashes ----------

def test_no_clashes_different_days():
    offerings = [
        _offering("o1", "ACC101", "Monday", "09:00", "11:00"),
        _offering("o2", "MGT101", "Tuesday", "09:00", "11:00"),
    ]
    assert detect_clashes(offerings) == []


def test_no_clashes_adjacent_times():
    offerings = [
        _offering("o1", "ACC101", "Monday", "09:00", "11:00"),
        _offering("o2", "MGT101", "Monday", "11:00", "13:00"),
    ]
    assert detect_clashes(offerings) == []


def test_clash_overlap():
    offerings = [
        _offering("o1", "ACC101", "Monday", "09:00", "11:00"),
        _offering("o2", "ACC201", "Monday", "10:00", "12:00"),
    ]
    clashes = detect_clashes(offerings)
    assert len(clashes) == 1
    assert clashes[0]["course_1"] == "ACC101"
    assert clashes[0]["course_2"] == "ACC201"


def test_clash_fully_contained():
    offerings = [
        _offering("o1", "ACC101", "Monday", "09:00", "12:00"),
        _offering("o2", "MGT101", "Monday", "10:00", "11:00"),
    ]
    clashes = detect_clashes(offerings)
    assert len(clashes) == 1


def test_clash_single_offering_no_clash():
    offerings = [_offering("o1", "ACC101", "Monday", "09:00", "11:00")]
    assert detect_clashes(offerings) == []


def test_clash_multiple_pairs():
    offerings = [
        _offering("o1", "ACC101", "Monday", "09:00", "11:00"),
        _offering("o2", "ACC201", "Monday", "10:00", "12:00"),  # clashes with o1
        _offering("o3", "MGT101", "Monday", "10:30", "12:30"),  # clashes with o1 and o2
    ]
    clashes = detect_clashes(offerings)
    assert len(clashes) == 3


# ---------- calculate_gpa ----------

def test_gpa_empty():
    assert calculate_gpa([]) == 0.0


def test_gpa_all_a():
    courses = [_completed("ACC101", "A", credits=15), _completed("MGT101", "A", credits=15)]
    assert calculate_gpa(courses) == 4.0


def test_gpa_mixed_grades():
    courses = [
        _completed("ACC101", "A", credits=15),   # 4.0 × 15 = 60
        _completed("MGT101", "B", credits=15),   # 3.0 × 15 = 45
    ]
    gpa = calculate_gpa(courses)
    assert gpa == pytest.approx(3.5, abs=0.01)


def test_gpa_wd_excluded():
    courses = [
        _completed("ACC101", "A", credits=15),
        _completed("MGT101", "WD", credits=15),  # WD = None points, excluded
    ]
    gpa = calculate_gpa(courses)
    assert gpa == 4.0  # Only ACC101 counts


def test_gpa_weighted_by_credits():
    courses = [
        _completed("ACC101", "A", credits=15),   # 4.0 × 15 = 60
        _completed("MGT101", "C", credits=30),   # 2.0 × 30 = 60
    ]
    # total = 120 / 45 = 2.67
    gpa = calculate_gpa(courses)
    assert gpa == pytest.approx(120 / 45, abs=0.01)


def test_semester_gpas_grouping():
    courses = [
        _completed("ACC101", "A", credits=15, year=2025, semester="S1"),
        _completed("MGT101", "B", credits=15, year=2025, semester="S2"),
        _completed("ECN101", "A-", credits=15, year=2026, semester="S1"),
    ]
    gpas = calculate_semester_gpas(courses)
    assert set(gpas.keys()) == {"2025-S1", "2025-S2", "2026-S1"}
    assert gpas["2025-S1"] == pytest.approx(GPA_POINTS["A"], abs=0.01)
    assert gpas["2025-S2"] == pytest.approx(GPA_POINTS["B"], abs=0.01)
    assert gpas["2026-S1"] == pytest.approx(GPA_POINTS["A-"], abs=0.01)


# ---------- calculate_registration_fees ----------

def _tuition_item(programme: str = "BCOM") -> FeeItem:
    return FeeItem(
        code="TUT001",
        description="Tuition Fee",
        amount_cents=300000,  # FJ$3000 full semester (4 courses)
        currency="FJD",
        applies_to=programme,
        fee_type="tuition",
    )


def _levy_item() -> FeeItem:
    return FeeItem(
        code="LEV001",
        description="Student Levy",
        amount_cents=5000,
        currency="FJD",
        applies_to="ALL",
        fee_type="levy",
    )


def test_fee_tuition_partial_load_2_courses():
    items = calculate_registration_fees("BCOM", 2, [_tuition_item()])
    tuition = next(i for i in items if i.fee_type == "tuition")
    # 300000 / 4 * 2 = 150000
    assert tuition.amount_cents == 150000


def test_fee_tuition_full_load_4_courses():
    items = calculate_registration_fees("BCOM", 4, [_tuition_item()])
    tuition = next(i for i in items if i.fee_type == "tuition")
    assert tuition.amount_cents == 300000


def test_fee_levy_included():
    items = calculate_registration_fees("BCOM", 2, [_tuition_item(), _levy_item()])
    assert any(i.fee_type == "levy" for i in items)


def test_fee_other_programme_tuition_not_included():
    bsci_tuition = FeeItem(
        code="TUT002",
        description="BSCI Tuition",
        amount_cents=280000,
        currency="FJD",
        applies_to="BSCI",
        fee_type="tuition",
    )
    items = calculate_registration_fees("BCOM", 2, [bsci_tuition, _levy_item()])
    # BSCI tuition should not appear; only ALL levy
    tuition_items = [i for i in items if i.fee_type == "tuition"]
    assert tuition_items == []
    assert any(i.fee_type == "levy" for i in items)


def test_fee_all_programme_tuition_matches():
    all_tuition = FeeItem(
        code="TUT000",
        description="General Tuition",
        amount_cents=320000,
        currency="FJD",
        applies_to="ALL",
        fee_type="tuition",
    )
    items = calculate_registration_fees("BCOM", 3, [all_tuition])
    tuition = next(i for i in items if i.fee_type == "tuition")
    assert tuition.amount_cents == 320000 // 4 * 3
