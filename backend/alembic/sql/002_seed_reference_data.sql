-- =============================================================================
-- 002_seed_reference_data.sql
-- Reference data required by the requirements:
--   FR-01  roles (Admin, Curriculum Committee Member, Faculty, Reviewer)
--   FR-05  valid course types
--   FR-10  configurable CO-PO mapping scale
--
-- Fixed UUIDs keep reference data stable across environments and tests.
-- =============================================================================

INSERT INTO roles (id, code, name, description) VALUES
    ('00000000-0000-0000-0000-000000000001', 'ADMIN',
     'Administrator', 'Full administrative access to the system.'),
    ('00000000-0000-0000-0000-000000000002', 'COMMITTEE_MEMBER',
     'Curriculum Committee Member', 'Reviews and approves curriculum, outcome, and mapping changes.'),
    ('00000000-0000-0000-0000-000000000003', 'FACULTY',
     'Faculty / Instructor', 'Creates and modifies curriculum content where authorized.'),
    ('00000000-0000-0000-0000-000000000004', 'REVIEWER',
     'Reviewer', 'Views verification reports and reviews AI findings.')
ON CONFLICT (code) DO NOTHING;

INSERT INTO course_types (id, code, name, description) VALUES
    ('00000000-0000-0000-0000-000000000101', 'CORE',
     'Core', 'Mandatory course of the program.'),
    ('00000000-0000-0000-0000-000000000102', 'ELECTIVE',
     'Elective', 'Optional or stream-elective course.'),
    ('00000000-0000-0000-0000-000000000103', 'LAB',
     'Laboratory', 'Practical / laboratory course.'),
    ('00000000-0000-0000-0000-000000000104', 'PROJECT',
     'Project', 'Project or capstone work.'),
    ('00000000-0000-0000-0000-000000000105', 'SEMINAR',
     'Seminar', 'Seminar or workshop course.'),
    ('00000000-0000-0000-0000-000000000106', 'INTERNSHIP',
     'Internship', 'Industry internship or training.')
ON CONFLICT (code) DO NOTHING;

-- Default institutional scale; configurable, not hard-coded (FR-10 Notes).
INSERT INTO mapping_levels (id, code, name, numeric_value, description, sort_order) VALUES
    ('00000000-0000-0000-0000-000000000201', 'LOW',    'Low',    1,
     'Slight contribution of the CO to the PO.', 1),
    ('00000000-0000-0000-0000-000000000202', 'MEDIUM', 'Medium', 2,
     'Moderate contribution of the CO to the PO.', 2),
    ('00000000-0000-0000-0000-000000000203', 'HIGH',   'High',   3,
     'Substantial contribution of the CO to the PO.', 3)
ON CONFLICT (code) DO NOTHING;
