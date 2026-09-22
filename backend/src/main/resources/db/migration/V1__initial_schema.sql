-- =============================================================================
-- V1__initial_schema.sql
-- AI-Powered Curriculum Intelligence & Verification Framework
-- PostgreSQL 16+
--
-- Implements the data model described in docs/lld/database-schema.md.
-- Requirements covered: FR-01 .. FR-12, NFR-01.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Shared trigger function: maintain updated_at on row updates
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS
$$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 1. Identity and access (FR-01)
-- =============================================================================

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(100) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(200) NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email),
    CONSTRAINT chk_users_status  CHECK (status IN ('ACTIVE', 'INACTIVE', 'LOCKED'))
);

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(50)  NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_roles_code UNIQUE (code)
);

CREATE TABLE user_roles (
    user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role_id     UUID NOT NULL REFERENCES roles (id),
    assigned_by UUID REFERENCES users (id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX idx_user_roles_role_id ON user_roles (role_id);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 2. Academic structure (FR-02)
-- =============================================================================

CREATE TABLE departments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code       VARCHAR(20)  NOT NULL,
    name       VARCHAR(200) NOT NULL,
    status     VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_departments_code UNIQUE (code),
    CONSTRAINT chk_departments_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE programs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id  UUID NOT NULL REFERENCES departments (id),
    code           VARCHAR(20)  NOT NULL,
    name           VARCHAR(200) NOT NULL,
    degree_type    VARCHAR(50),
    duration_years NUMERIC(3, 1) NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_programs_code       UNIQUE (code),
    CONSTRAINT chk_programs_duration  CHECK (duration_years > 0),
    CONSTRAINT chk_programs_status    CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE INDEX idx_programs_department_id ON programs (department_id);

CREATE TRIGGER trg_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_programs_updated_at
    BEFORE UPDATE ON programs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 3. Curriculum and versioning (FR-02, FR-03, FR-04)
-- =============================================================================

CREATE TABLE curricula (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id     UUID NOT NULL REFERENCES programs (id),
    academic_year  VARCHAR(20)  NOT NULL,
    regulation     VARCHAR(50)  NOT NULL,
    title          VARCHAR(200),
    duration_years NUMERIC(3, 1) NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_by     UUID NOT NULL REFERENCES users (id),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_curricula_program_regulation UNIQUE (program_id, regulation),
    CONSTRAINT chk_curricula_duration CHECK (duration_years > 0),
    CONSTRAINT chk_curricula_status   CHECK (status IN ('ACTIVE', 'ARCHIVED'))
);

CREATE TABLE curriculum_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id       UUID NOT NULL REFERENCES curricula (id) ON DELETE CASCADE,
    version_label       VARCHAR(20) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    previous_version_id UUID REFERENCES curriculum_versions (id),
    change_summary      TEXT,
    created_by          UUID NOT NULL REFERENCES users (id),
    published_by        UUID REFERENCES users (id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at        TIMESTAMPTZ,
    CONSTRAINT uq_curriculum_versions UNIQUE (curriculum_id, version_label),
    CONSTRAINT chk_curriculum_versions_status CHECK (
        status IN ('DRAFT', 'UNDER_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED')
    )
);

CREATE TABLE semesters (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_version_id UUID NOT NULL REFERENCES curriculum_versions (id) ON DELETE CASCADE,
    semester_number       SMALLINT NOT NULL,
    name                  VARCHAR(100),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_semesters UNIQUE (curriculum_version_id, semester_number),
    CONSTRAINT uq_semesters_id_version UNIQUE (id, curriculum_version_id),
    CONSTRAINT chk_semesters_number CHECK (semester_number > 0)
);

CREATE INDEX idx_curricula_program_id ON curricula (program_id);
CREATE INDEX idx_curriculum_versions_curriculum_id ON curriculum_versions (curriculum_id, status);

CREATE TRIGGER trg_curricula_updated_at
    BEFORE UPDATE ON curricula
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_curriculum_versions_updated_at
    BEFORE UPDATE ON curriculum_versions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 4. Courses and course outcomes (FR-05, FR-06, FR-07)
-- =============================================================================

CREATE TABLE course_types (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(30)  NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_course_types_code UNIQUE (code)
);

CREATE TABLE courses (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_version_id UUID NOT NULL REFERENCES curriculum_versions (id) ON DELETE CASCADE,
    semester_id           UUID NOT NULL,
    course_code           VARCHAR(30)  NOT NULL,
    course_name           VARCHAR(200) NOT NULL,
    course_type_id        UUID NOT NULL REFERENCES course_types (id),
    credits               NUMERIC(4, 1) NOT NULL,
    contact_hours         INTEGER,
    description           TEXT,
    syllabus              TEXT,
    status                VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by            UUID NOT NULL REFERENCES users (id),
    updated_by            UUID REFERENCES users (id),
    removed_by            UUID REFERENCES users (id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at            TIMESTAMPTZ,
    CONSTRAINT uq_courses_id_version UNIQUE (id, curriculum_version_id),
    CONSTRAINT fk_courses_semester FOREIGN KEY (semester_id, curriculum_version_id)
        REFERENCES semesters (id, curriculum_version_id),
    CONSTRAINT chk_courses_credits CHECK (credits > 0),
    CONSTRAINT chk_courses_hours   CHECK (contact_hours IS NULL OR contact_hours >= 0),
    CONSTRAINT chk_courses_status  CHECK (status IN ('ACTIVE', 'REMOVED'))
);

CREATE UNIQUE INDEX uq_courses_code_active
    ON courses (curriculum_version_id, course_code)
    WHERE status = 'ACTIVE';

CREATE INDEX idx_courses_version        ON courses (curriculum_version_id);
CREATE INDEX idx_courses_version_status ON courses (curriculum_version_id, status);
CREATE INDEX idx_courses_semester       ON courses (semester_id);
CREATE INDEX idx_courses_type           ON courses (course_type_id);

CREATE TABLE course_outcomes (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id             UUID NOT NULL,
    curriculum_version_id UUID NOT NULL,
    co_code               VARCHAR(30) NOT NULL,
    description           TEXT NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by            UUID NOT NULL REFERENCES users (id),
    updated_by            UUID REFERENCES users (id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_course_outcomes_id_version UNIQUE (id, curriculum_version_id),
    CONSTRAINT fk_course_outcomes_course FOREIGN KEY (course_id, curriculum_version_id)
        REFERENCES courses (id, curriculum_version_id) ON DELETE CASCADE,
    CONSTRAINT chk_course_outcomes_status      CHECK (status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT chk_course_outcomes_description CHECK (btrim(description) <> '')
);

CREATE UNIQUE INDEX uq_course_outcomes_code_active
    ON course_outcomes (course_id, co_code)
    WHERE status = 'ACTIVE';

CREATE INDEX idx_course_outcomes_course  ON course_outcomes (course_id);
CREATE INDEX idx_course_outcomes_version ON course_outcomes (curriculum_version_id);

CREATE TRIGGER trg_courses_updated_at
    BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_course_outcomes_updated_at
    BEFORE UPDATE ON course_outcomes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 5. Program outcomes and PEOs (FR-08, FR-09)
-- =============================================================================

CREATE TABLE program_outcomes (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES programs (id),
    po_code    VARCHAR(30) NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by UUID NOT NULL REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_program_outcomes_code UNIQUE (program_id, po_code),
    CONSTRAINT chk_program_outcomes_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE program_outcome_versions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_outcome_id UUID NOT NULL REFERENCES program_outcomes (id) ON DELETE CASCADE,
    version_number     INTEGER NOT NULL,
    description        TEXT NOT NULL,
    effective_date     DATE,
    status             VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    review_comments    TEXT,
    created_by         UUID NOT NULL REFERENCES users (id),
    approved_by        UUID REFERENCES users (id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at        TIMESTAMPTZ,
    CONSTRAINT uq_program_outcome_versions      UNIQUE (program_outcome_id, version_number),
    CONSTRAINT uq_program_outcome_versions_id_po UNIQUE (id, program_outcome_id),
    CONSTRAINT chk_po_versions_status      CHECK (
        status IN ('DRAFT', 'PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED')
    ),
    CONSTRAINT chk_po_versions_description CHECK (btrim(description) <> '')
);

CREATE UNIQUE INDEX uq_po_versions_approved
    ON program_outcome_versions (program_outcome_id)
    WHERE status = 'APPROVED';

CREATE INDEX idx_po_versions_po ON program_outcome_versions (program_outcome_id, status);

CREATE TABLE program_educational_objectives (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES programs (id),
    peo_code   VARCHAR(30) NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by UUID NOT NULL REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_peos_code UNIQUE (program_id, peo_code),
    CONSTRAINT chk_peos_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE peo_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    peo_id          UUID NOT NULL REFERENCES program_educational_objectives (id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    description     TEXT NOT NULL,
    effective_date  DATE,
    status          VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    review_comments TEXT,
    created_by      UUID NOT NULL REFERENCES users (id),
    approved_by     UUID REFERENCES users (id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at     TIMESTAMPTZ,
    CONSTRAINT uq_peo_versions       UNIQUE (peo_id, version_number),
    CONSTRAINT uq_peo_versions_id_peo UNIQUE (id, peo_id),
    CONSTRAINT chk_peo_versions_status CHECK (
        status IN ('DRAFT', 'PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED')
    ),
    CONSTRAINT chk_peo_versions_description CHECK (btrim(description) <> '')
);

CREATE UNIQUE INDEX uq_peo_versions_approved
    ON peo_versions (peo_id)
    WHERE status = 'APPROVED';

CREATE INDEX idx_peo_versions_peo ON peo_versions (peo_id, status);

-- Which PO / PEO version applies to a curriculum version (FR-08-05, FR-09-05)

CREATE TABLE curriculum_version_program_outcomes (
    curriculum_version_id      UUID NOT NULL REFERENCES curriculum_versions (id) ON DELETE CASCADE,
    program_outcome_id         UUID NOT NULL REFERENCES program_outcomes (id),
    program_outcome_version_id UUID NOT NULL,
    added_by                   UUID NOT NULL REFERENCES users (id),
    added_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (curriculum_version_id, program_outcome_id),
    CONSTRAINT fk_cvpo_version FOREIGN KEY (program_outcome_version_id, program_outcome_id)
        REFERENCES program_outcome_versions (id, program_outcome_id)
);

CREATE TABLE curriculum_version_peos (
    curriculum_version_id UUID NOT NULL REFERENCES curriculum_versions (id) ON DELETE CASCADE,
    peo_id                UUID NOT NULL REFERENCES program_educational_objectives (id),
    peo_version_id        UUID NOT NULL,
    added_by              UUID NOT NULL REFERENCES users (id),
    added_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (curriculum_version_id, peo_id),
    CONSTRAINT fk_cvpeo_version FOREIGN KEY (peo_version_id, peo_id)
        REFERENCES peo_versions (id, peo_id)
);

CREATE INDEX idx_cvpo_po    ON curriculum_version_program_outcomes (program_outcome_id);
CREATE INDEX idx_cvpeo_peo  ON curriculum_version_peos (peo_id);

CREATE TRIGGER trg_program_outcomes_updated_at
    BEFORE UPDATE ON program_outcomes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_peos_updated_at
    BEFORE UPDATE ON program_educational_objectives
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 6. CO-PO mapping (FR-10)
-- =============================================================================

CREATE TABLE mapping_levels (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code          VARCHAR(20)  NOT NULL,
    name          VARCHAR(100) NOT NULL,
    numeric_value SMALLINT NOT NULL,
    description   VARCHAR(500),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order    SMALLINT NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mapping_levels_code    UNIQUE (code),
    CONSTRAINT uq_mapping_levels_numeric UNIQUE (numeric_value),
    CONSTRAINT chk_mapping_levels_numeric CHECK (numeric_value > 0)
);

CREATE TABLE co_po_mappings (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_version_id UUID NOT NULL REFERENCES curriculum_versions (id) ON DELETE CASCADE,
    course_outcome_id     UUID NOT NULL,
    program_outcome_id    UUID NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by            UUID NOT NULL REFERENCES users (id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_co_po_mappings_co FOREIGN KEY (course_outcome_id, curriculum_version_id)
        REFERENCES course_outcomes (id, curriculum_version_id),
    CONSTRAINT fk_co_po_mappings_po FOREIGN KEY (curriculum_version_id, program_outcome_id)
        REFERENCES curriculum_version_program_outcomes (curriculum_version_id, program_outcome_id),
    CONSTRAINT chk_co_po_mappings_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE UNIQUE INDEX uq_co_po_mappings_active
    ON co_po_mappings (curriculum_version_id, course_outcome_id, program_outcome_id)
    WHERE status = 'ACTIVE';

CREATE INDEX idx_co_po_mappings_version ON co_po_mappings (curriculum_version_id);
CREATE INDEX idx_co_po_mappings_co      ON co_po_mappings (course_outcome_id);
CREATE INDEX idx_co_po_mappings_po      ON co_po_mappings (program_outcome_id);

CREATE TABLE co_po_mapping_versions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_id       UUID NOT NULL REFERENCES co_po_mappings (id) ON DELETE CASCADE,
    version_number   INTEGER NOT NULL,
    mapping_level_id UUID NOT NULL REFERENCES mapping_levels (id),
    effective_date   DATE,
    status           VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    review_comments  TEXT,
    created_by       UUID NOT NULL REFERENCES users (id),
    approved_by      UUID REFERENCES users (id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at      TIMESTAMPTZ,
    CONSTRAINT uq_co_po_mapping_versions UNIQUE (mapping_id, version_number),
    CONSTRAINT chk_co_po_mapping_versions_status CHECK (
        status IN ('DRAFT', 'PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED')
    )
);

CREATE UNIQUE INDEX uq_co_po_mapping_versions_approved
    ON co_po_mapping_versions (mapping_id)
    WHERE status = 'APPROVED';

CREATE INDEX idx_co_po_mapping_versions_mapping ON co_po_mapping_versions (mapping_id, status);

CREATE TRIGGER trg_co_po_mappings_updated_at
    BEFORE UPDATE ON co_po_mappings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 7. Prerequisites (FR-11)
-- =============================================================================

CREATE TABLE course_prerequisites (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_version_id  UUID NOT NULL REFERENCES curriculum_versions (id) ON DELETE CASCADE,
    prerequisite_course_id UUID NOT NULL,
    target_course_id       UUID NOT NULL,
    status                 VARCHAR(20) NOT NULL DEFAULT 'PROPOSED',
    review_comments        TEXT,
    created_by             UUID NOT NULL REFERENCES users (id),
    approved_by            UUID REFERENCES users (id),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at            TIMESTAMPTZ,
    CONSTRAINT fk_course_prerequisites_prereq FOREIGN KEY (prerequisite_course_id, curriculum_version_id)
        REFERENCES courses (id, curriculum_version_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_prerequisites_target FOREIGN KEY (target_course_id, curriculum_version_id)
        REFERENCES courses (id, curriculum_version_id) ON DELETE CASCADE,
    CONSTRAINT chk_course_prerequisites_not_self CHECK (prerequisite_course_id <> target_course_id),
    CONSTRAINT chk_course_prerequisites_status CHECK (
        status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'REMOVED')
    )
);

CREATE UNIQUE INDEX uq_course_prerequisites_active
    ON course_prerequisites (curriculum_version_id, prerequisite_course_id, target_course_id)
    WHERE status IN ('PROPOSED', 'APPROVED');

CREATE INDEX idx_course_prerequisites_prereq ON course_prerequisites (prerequisite_course_id);
CREATE INDEX idx_course_prerequisites_target ON course_prerequisites (target_course_id);

CREATE TRIGGER trg_course_prerequisites_updated_at
    BEFORE UPDATE ON course_prerequisites
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 8. Verification runs and findings (NFR-01)
-- =============================================================================

CREATE TABLE verification_runs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_version_id UUID NOT NULL REFERENCES curriculum_versions (id),
    requested_by          UUID NOT NULL REFERENCES users (id),
    status                VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    requested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at            TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,
    error_message         TEXT,
    summary               JSONB,
    CONSTRAINT chk_verification_runs_status CHECK (
        status IN ('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED')
    )
);

CREATE INDEX idx_verification_runs_version ON verification_runs (curriculum_version_id, status);
CREATE INDEX idx_verification_runs_status  ON verification_runs (status);

CREATE TABLE verification_findings (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_run_id   UUID NOT NULL REFERENCES verification_runs (id) ON DELETE CASCADE,
    category              VARCHAR(50) NOT NULL,
    severity              VARCHAR(20) NOT NULL,
    confidence            NUMERIC(4, 3),
    title                 VARCHAR(300) NOT NULL,
    description           TEXT,
    evidence              TEXT,
    recommendation        TEXT,
    requires_human_review BOOLEAN NOT NULL DEFAULT TRUE,
    review_status         VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    reviewed_by           UUID REFERENCES users (id),
    reviewed_at           TIMESTAMPTZ,
    review_comments       TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_verification_findings_category CHECK (
        category IN ('STRUCTURAL', 'OUTCOME', 'DEPENDENCY', 'CONTENT',
                     'INDUSTRY_ALIGNMENT', 'ACCREDITATION_OBE')
    ),
    CONSTRAINT chk_verification_findings_severity CHECK (
        severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
    ),
    CONSTRAINT chk_verification_findings_confidence CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    ),
    CONSTRAINT chk_verification_findings_review_status CHECK (
        review_status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'MODIFIED')
    )
);

CREATE INDEX idx_verification_findings_run      ON verification_findings (verification_run_id);
CREATE INDEX idx_verification_findings_category ON verification_findings (category, severity);
CREATE INDEX idx_verification_findings_review   ON verification_findings (review_status);

CREATE TABLE verification_finding_references (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id  UUID NOT NULL REFERENCES verification_findings (id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id   UUID NOT NULL,
    note        VARCHAR(500),
    CONSTRAINT chk_finding_refs_entity_type CHECK (
        entity_type IN ('CURRICULUM_VERSION', 'SEMESTER', 'COURSE', 'COURSE_OUTCOME',
                        'PROGRAM_OUTCOME', 'PEO', 'CO_PO_MAPPING', 'PREREQUISITE')
    )
);

CREATE INDEX idx_finding_refs_finding ON verification_finding_references (finding_id);
CREATE INDEX idx_finding_refs_entity  ON verification_finding_references (entity_type, entity_id);

-- =============================================================================
-- 9. Audit history (FR-06, FR-07, BR-PO-07, BR-PEO-07, BR-COPO-08, BR-PR-08)
-- =============================================================================

CREATE TABLE audit_logs (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type           VARCHAR(50) NOT NULL,
    entity_id             UUID,
    action                VARCHAR(50) NOT NULL,
    actor_user_id         UUID REFERENCES users (id),
    curriculum_version_id UUID REFERENCES curriculum_versions (id),
    old_values            JSONB,
    new_values            JSONB,
    metadata              JSONB,
    occurred_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_entity    ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_logs_actor     ON audit_logs (actor_user_id);
CREATE INDEX idx_audit_logs_version   ON audit_logs (curriculum_version_id);
CREATE INDEX idx_audit_logs_occurred  ON audit_logs (occurred_at);
