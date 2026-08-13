import os

from direhire.ai.contracts import (
    JOB_DEMAND_SCHEMA_VERSION,
    DemandCluster,
    JobConstraint,
    JobDemandProfileContent,
    RequirementCategory,
    RoleReality,
    SeniorityAssessment,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "jobthai", "1945537")


def test_v2_schema_contract_instantiation() -> None:
    assert JOB_DEMAND_SCHEMA_VERSION == 2

    # Instantiate V2 sub-models directly to verify strict schema validation
    reality = RoleReality(
        headline="Broad IT Support and Infrastructure Generalist",
        primary_archetype="HANDS_ON_IT_GENERALIST",
        primary_occupation="IT Support Specialist",
        secondary_occupations=["Systems Support Specialist", "Network Support Specialist"],
        title_alignment="UNDERSTATES_SCOPE",
        primary_mission="Keep internal users, endpoints, networks, and IT assets operational.",
        breadth="BROAD",
    )
    assert reality.primary_archetype == "HANDS_ON_IT_GENERALIST"
    assert reality.title_alignment == "UNDERSTATES_SCOPE"

    seniority = SeniorityAssessment(
        assessment="EARLY_CAREER_TO_MID",
        explicit_min_years=1.0,
        explicit_max_years=3.0,
        interpretation_confidence="HIGH",
        reason="Employer asks for 1-3 years of related IT support experience.",
    )
    assert seniority.assessment == "EARLY_CAREER_TO_MID"

    cluster = DemandCluster(
        name="Network and cabling infrastructure",
        priority="CORE",
        reason="Role is responsible for LAN wiring and RJ45 crimping.",
        evidence="เดินสาย LAN พร้อมเข้าหัว RJ ได้",
        evidence_strength="EXPLICIT",
    )
    assert cluster.priority == "CORE"
    assert cluster.evidence == "เดินสาย LAN พร้อมเข้าหัว RJ ได้"


def test_v2_job_analysis_document_structure() -> None:
    txt_path = os.path.join(FIXTURES_DIR, "extracted-original.txt")
    assert os.path.exists(txt_path)

    with open(txt_path, encoding="utf-8") as f:
        extracted_text = f.read()

    # Unmistakable phrase presence in fixture
    assert "เดินสาย LAN" in extracted_text
    assert "อายุระหว่าง 22-30 ปี" in extracted_text

    # Construct complete valid JobDemandProfileContent V2 instance
    content = JobDemandProfileContent(
        role_summary=(
            "Broad early-career IT Operations role combining end-user support, networking, "
            "and IT asset lifecycle management."
        ),
        role_reality=RoleReality(
            headline="Broad IT Support and Infrastructure Generalist",
            primary_archetype="HANDS_ON_IT_GENERALIST",
            primary_occupation="IT Support Specialist",
            secondary_occupations=["Network Support", "Systems Admin Assistant"],
            title_alignment="UNDERSTATES_SCOPE",
            primary_mission=("Maintain workplace endpoints, internal networks, and IT equipment."),
            breadth="BROAD",
        ),
        seniority=SeniorityAssessment(
            assessment="EARLY_CAREER_TO_MID",
            explicit_min_years=1.0,
            explicit_max_years=3.0,
            interpretation_confidence="HIGH",
            reason="Requires 1-3 years of related IT experience.",
        ),
        demand_clusters=[
            DemandCluster(
                name="End-user and Windows support",
                priority="CORE",
                reason="Primary duty assisting staff and troubleshooting OS/software",
                evidence="ให้คำปรึกษากับพนักงานในบริษัทด้านคอมพิวเตอร์",
                evidence_strength="EXPLICIT",
            ),
            DemandCluster(
                name="Network and cabling operations",
                priority="CORE",
                reason="Responsible for LAN cabling and RJ45 crimping",
                evidence="เดินสาย LAN พร้อมเข้าหัว RJ ได้",
                evidence_strength="EXPLICIT",
            ),
        ],
        competencies=[],
        responsibility_clusters=[],
        requirements=[
            RequirementCategory(
                category="ELIGIBILITY",
                title="Bachelor's degree in IT / Computer Science or related field",
                evidence="วุฒิปริญญาตรีขึ้นไป สาขาเทคโนโลยีสารสนเทศ",
                evidence_strength="EXPLICIT",
            )
        ],
        job_constraints=[
            JobConstraint(
                constraint_type="LOCATION",
                description="Physical presence at Lat Phrao 94 / Wang Thonglang office",
                evidence_strength="EXPLICIT",
            )
        ],
        work_location_summary={
            "value": "Wang Thonglang, Bangkok",
            "evidence": "1213/251 ชั้นที่ 2 ซอยลาดพร้าว 94",
            "evidence_strength": "EXPLICIT",
            "interpretation_confidence": "HIGH",
        },
        work_arrangement_summary={
            "value": "On-site workplace presence",
            "evidence": "ปฏิบัติงาน ณ สำนักงาน",
            "evidence_strength": "STRONGLY_IMPLIED",
            "interpretation_confidence": "HIGH",
        },
        remote_eligibility="UNCLEAR",
        real_work_scenarios=[
            "A user reports network connectivity loss. You inspect workstation, test LAN cable, "
            "re-crimp an RJ45 connector if needed, and restore user access."
        ],
        contradictions=[],
        overall_confidence="HIGH",
    )

    data = content.model_dump(mode="json")
    assert data["role_reality"]["primary_archetype"] == "HANDS_ON_IT_GENERALIST"
    assert data["seniority"]["assessment"] == "EARLY_CAREER_TO_MID"
    assert data["demand_clusters"][0]["priority"] == "CORE"
