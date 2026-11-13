# LLD: Curriculum Structure and Outcome Verification (FR-14)

## 1. Scope and composition

`VerificationService` runs one version-scoped analysis that combines:

- the prerequisite analyzer defined in FR-12;
- structure, semester, credit, and distribution checks;
- deterministic topic overlap/progression detection;
- outcome coverage checks;
- comparison against governed reference data.

The analyzer is read-only and advisory. Findings are persisted through
`verification_runs`, `verification_findings`, and
`verification_finding_references`. Governed reference definitions are stored in
`verification_references` (migration `0006_verification_references.py`).

The service never edits curriculum, course, outcome, prerequisite, mapping, or
reference data. Every finding has `requires_human_review = true` and defaults to
`PENDING`.

## 2. Input snapshot

`_load_snapshot()` builds an immutable `_VersionSnapshot` for the selected
`CurriculumVersion`:

- Curriculum metadata and the selected version metadata.
- All semesters of the version, ordered by `semester_number`.
- All courses of the version, including removed courses, keyed by id.
- Prerequisite rows with status `PROPOSED`, `APPROVED`, or `REJECTED`.
  `PROPOSED` and `APPROVED` rows form the active graph.
- Active course outcomes of active courses.
- Active program outcomes and PEOs pinned to the version.
- Active `CoPoMapping` rows and their mapping-version history. A mapping
  contributes to coverage only when its latest mapping version is `APPROVED`,
  its course outcome is active, and its program outcome is active and pinned.
- Active governed references resolved for the curriculum's program.

All reads are constrained to the selected version or to records pinned by that
version. Historical versions therefore use their own data.

## 3. Fingerprint and stale detection

The snapshot carries a SHA-256 fingerprint computed over canonical JSON
(`sort_keys=True`, compact separators). Fingerprint inputs are:

- selected version id, label, status, and predecessor id;
- curriculum id, program id, regulation, and duration;
- semester ids, numbers, names, and focus text;
- course ids, codes, names, types, credits, semester, contact hours,
  description, syllabus, status, and `updated_at`;
- course outcome ids, course ids, codes, descriptions, statuses, and
  `updated_at`;
- analyzed prerequisite rows (including `REJECTED`) and their review comments
  and `updated_at`;
- pinned PO/PEO ids and pinned outcome version ids;
- mappings, mapping status, mapping-version ids, numbers, levels, and statuses;
- applicable active governed references, including their rules.

The summary stores `input_fingerprint` and `input_fingerprint_version = 1`.
`VerificationRunResponse` exposes `input_fingerprint` and `is_stale`.

`is_stale` is true only when the run has a stored fingerprint and the current
snapshot fingerprint differs. Runs created before fingerprinting (no stored
fingerprint) are reported as not stale. `list_runs`, `get_run`, and `get_report`
recompute the current fingerprint; a stale run remains unchanged and the user
must start a new run.

## 4. Checks and stable evidence codes

Every finding begins its `evidence` with a stable check code so repeated runs
can be compared independently of titles.

### 4.1 Prerequisite and dependency checks

| Check code | Condition | Category / severity |
| --- | --- | --- |
| `SELF_PREREQUISITE` | Prerequisite row references the same course on both sides | `DEPENDENCY` / `CRITICAL` |
| `MISSING_PREREQUISITE_COURSE` | Prerequisite row references a course absent from the version | `STRUCTURAL` / `HIGH` |
| `REMOVED_PREREQUISITE_COURSE` | Prerequisite involves a course whose status is not `ACTIVE` | `STRUCTURAL` / `MEDIUM` |
| `DUPLICATE_PREREQUISITE` | More than one analyzed row exists for the same prerequisite pair | `STRUCTURAL` / `LOW` |
| `CIRCULAR_PREREQUISITE` | Active graph contains a cycle | `DEPENDENCY` / `CRITICAL` |
| `PREREQUISITE_OUT_OF_ORDER` | Target is scheduled before its prerequisite | `DEPENDENCY` / `MEDIUM` |
| `PREREQUISITE_SAME_SEMESTER` | Target and prerequisite share a semester | `DEPENDENCY` / `LOW` |
| `MISSING_PREREQUISITE_CANDIDATE` | A later course in a participating discipline has no incoming prerequisite | `DEPENDENCY` / `INFO` |
| `TRANSITIVE_PREREQUISITE` | A direct prerequisite edge is already implied by a longer path | `DEPENDENCY` / `INFO` |

Cycle detection canonicalizes rotations so each loop is reported once.
Transitive redundancy excludes the direct edge while searching for an
alternative path, and reports the full path plus all involved relationship ids.

### 4.2 Structure, semester, and credit checks

| Check code | Condition | Category / severity |
| --- | --- | --- |
| `INVALID_COURSE_CREDITS` | Active course credits are `<= 0` or `> 30` | `STRUCTURAL` / `HIGH` |
| `CURRICULUM_WITHOUT_ACTIVE_COURSES` | Version has no active courses | `STRUCTURAL` / `HIGH` |
| `EMPTY_SEMESTER` | Semester has no active courses | `STRUCTURAL` / `INFO` |
| `SEMESTER_SEQUENCE_GAP` | Semester numbers are not contiguous from 1 | `STRUCTURAL` / `LOW` |

The structure summary is always produced, even when findings exist:

- `active_course_count`, `semester_count`, `expected_semester_count` (duration
  in years × 2 when duration is available);
- `total_credits`, `average_semester_credits`;
- `credit_totals_by_semester`, `credits_by_course_type`;
- `course_counts_by_semester`, `course_counts_by_course_type`;
- `semester_credit_range` with `min` and `max`.

These values describe the curriculum; they do not assert compliance unless a
governed institutional reference supplies a target.

### 4.3 Topic overlap and progression

Topic profiles are built from the course name, description, syllabus, and active
course outcome descriptions. `verification_analysis.py` tokenizes lower-case
alphanumeric words, removes stopwords and short tokens, and applies a small
deterministic stemmer. Similarity combines Jaccard and containment:

```text
score = 0.6 * jaccard + 0.4 * containment
```

Candidate thresholds:

- each profile must contain at least 5 terms;
- at least 3 shared terms;
- score at least 0.35.

Classification, in order:

1. **Same semester:** `REDUNDANCY` when score ≥ 0.55 or title similarity
   ≥ 0.75; otherwise `CROSS_DISCIPLINE`.
2. **Later semester with a prerequisite path:** the earlier course must be in
   the later course's transitive upstream set → `PROGRESSION`; no finding.
3. **Same course-code prefix and progression evidence:** progression marker in
   the later course name (`advanced`, `capstone`, `project`, `seminar`,
   `internship`, `special topics`, `II`–`IV`), a higher numeric course code, or
   score ≥ 0.5 → `PROGRESSION_UNVERIFIED`.
4. **Strong evidence otherwise:** score ≥ 0.6 and title similarity ≥ 0.55 →
   `REDUNDANCY`.
5. Otherwise `CROSS_DISCIPLINE`.

Findings:

| Check code | Condition | Category / severity |
| --- | --- | --- |
| `TOPIC_REDUNDANCY` | Classified `REDUNDANCY` | `CONTENT` / `MEDIUM` when score ≥ 0.55 or title similarity ≥ 0.7, otherwise `LOW` |
| `TOPIC_PROGRESSION` | Classified `PROGRESSION_UNVERIFIED` | `CONTENT` / `INFO` |
| `TOPIC_OVERLAP` | Strong cross-discipline overlap (score ≥ 0.6 and title similarity ≥ 0.55) | `CONTENT` / `INFO` |

The evidence records both course codes, semesters, shared terms, score, and
title similarity. Findings reference both courses and both semesters. The topic
summary reports `pairs_evaluated`, `candidates`, `redundancy_candidates`,
`progression_candidates`, `unverified_progression_candidates`,
`cross_discipline_candidates`, and the top 10 overlaps.

### 4.4 Outcome coverage

| Check code | Condition | Category / severity |
| --- | --- | --- |
| `COURSE_WITHOUT_CO` | Active course has no active course outcome | `OUTCOME` / `MEDIUM` |
| `CO_WITHOUT_APPROVED_PO` | Active CO has no qualifying approved mapping to a pinned active PO | `OUTCOME` / `MEDIUM` |
| `PO_WITHOUT_APPROVED_CO` | Pinned active PO has no qualifying approved mapping from an active CO | `OUTCOME` / `MEDIUM` |

### 4.5 Governed reference comparison

`verification_references` stores validated JSON rules. Rules are validated with
Pydantic models in `app/schemas/verification_reference.py`; unknown fields are
rejected.

#### Institutional rules

```json
{
  "total_credits": {"min": 120, "max": 140},
  "semester_credits": {"min": 15, "max": 24},
  "semester_count": {"min": 8, "max": 8},
  "course_type_credits": {"CORE": {"min": 60}},
  "course_type_share": {"ELECTIVE": {"min": 0.15, "max": 0.3}}
}
```

| Check code | Condition |
| --- | --- |
| `INSTITUTIONAL_TOTAL_CREDITS` | Total active credits outside the configured range |
| `INSTITUTIONAL_SEMESTER_CREDITS` | Any semester's active credits outside the configured range |
| `INSTITUTIONAL_SEMESTER_COUNT` | Semester count outside the configured range |
| `INSTITUTIONAL_COURSE_TYPE_CREDITS` | Credits for a course type outside the configured range |
| `INSTITUTIONAL_COURSE_TYPE_SHARE` | Credit share for a course type outside the configured range |

Category is `STRUCTURAL`; severity comes from the reference.

#### OBE rules

```json
{
  "required_po_codes": ["PO1", "PO2"],
  "required_peo_codes": ["PEO1"],
  "min_po_coverage_ratio": 0.8,
  "min_approved_mapping_ratio": 0.75
}
```

| Check code | Condition |
| --- | --- |
| `OBE_PO_REQUIRED` | A required PO code is not active and pinned |
| `OBE_PEO_REQUIRED` | A required PEO code is not active and pinned |
| `OBE_PO_COVERAGE` | Approved coverage of pinned POs is below the target |
| `OBE_MAPPING_COVERAGE` | Approved coverage of active COs is below the target |

Category is `ACCREDITATION_OBE`; severity comes from the reference.

#### Accreditation rules

```json
{
  "criterion": "Criterion 4 – Curriculum",
  "required_po_codes": ["PO1"],
  "required_course_types": ["CORE", "LAB"],
  "min_po_coverage_ratio": 0.8,
  "min_approved_mapping_ratio": 0.7
}
```

| Check code | Condition |
| --- | --- |
| `ACCREDITATION_PO_REQUIRED` | A required PO code is not active and pinned |
| `ACCREDITATION_COURSE_TYPE_REQUIRED` | A required course type has no active course |
| `ACCREDITATION_PO_COVERAGE` | Approved PO coverage is below the target |
| `ACCREDITATION_MAPPING_COVERAGE` | Approved CO coverage is below the target |

Category is `ACCREDITATION_OBE`; severity comes from the reference.

#### Industry rules

```json
{
  "skills": [
    {
      "code": "CLOUD",
      "label": "Cloud deployment",
      "keywords": ["cloud", "kubernetes", "aws"],
      "required": true,
      "min_courses": 1
    }
  ],
  "min_required_skill_coverage_ratio": 0.8
}
```

| Check code | Condition | Confidence |
| --- | --- | --- |
| `INDUSTRY_SKILL_COVERAGE` | A required skill is evidenced in fewer than `min_courses` courses | `0.800` |
| `INDUSTRY_SKILL_TOTAL` | Required-skill coverage is below the target | `0.850` |

Category is `INDUSTRY_ALIGNMENT`; severity comes from the reference. Keyword
matching is word-boundary based and tolerates simple plural forms.

#### Reference precedence

1. Only `ACTIVE` references applicable to the program are loaded: global
   references (`program_id IS NULL`) plus references for the curriculum's
   program.
2. For each `(reference_type, code)`, the selected reference is the last one
   after sorting by program-specificity, effective date, and creation time.
   A program-specific reference therefore overrides a global reference with the
   same type and code, and a newer version overrides an older one.
3. The resolved set is filtered to one reference per type/code and used in the
   analysis and fingerprint.

Duplicate `(program_id, reference_type, code, version_label)` rows are rejected
by the service and database constraint.

Malformed rules that pass creation (for example after a schema change) are
skipped during analysis and listed under `reference_comparison.invalid_references`
with a reason; a malformed reference does not fail the whole run.

## 5. Summary contract

`_build_summary()` produces:

```json
{
  "result": "PASSED | ISSUES_FOUND",
  "total_findings": 12,
  "findings_by_severity": {"INFO": 3, "LOW": 2, "MEDIUM": 5, "HIGH": 1, "CRITICAL": 1},
  "findings_by_category": {"DEPENDENCY": 4, "STRUCTURAL": 3},
  "analyzers": [
    "PREREQUISITE",
    "CONTENT",
    "STRUCTURE",
    "OUTCOME_COVERAGE",
    "REFERENCE_COMPARISON"
  ],
  "prerequisite_graph": {
    "edge_count": 6,
    "root_courses": ["CS101"],
    "leaf_courses": ["CS401"],
    "isolated_courses": [],
    "longest_chain": ["CS101", "CS201", "CS301"],
    "longest_chain_length": 3,
    "longest_chain_semesters": [1, 2, 3],
    "transitive_redundant_edges": 1
  },
  "structure": {
    "active_course_count": 8,
    "semester_count": 8,
    "expected_semester_count": 8,
    "total_credits": 160,
    "credit_totals_by_semester": {"1": 20},
    "credits_by_course_type": {"CORE": 100},
    "course_counts_by_semester": {"1": 5},
    "course_counts_by_course_type": {"CORE": 6},
    "average_semester_credits": 20,
    "semester_credit_range": {"min": 18, "max": 22}
  },
  "credit_totals_by_semester": {"1": 20},
  "total_credits": 160,
  "credits_by_course_type": {"CORE": 100},
  "topic_overlap": {
    "pairs_evaluated": 28,
    "candidates": 3,
    "redundancy_candidates": 1,
    "progression_candidates": 1,
    "unverified_progression_candidates": 1,
    "cross_discipline_candidates": 0,
    "top_overlaps": []
  },
  "reference_comparison": {
    "status": "EVALUATED | NOT_CONFIGURED",
    "checked": true,
    "count": 2,
    "references": [],
    "findings_by_reference": {},
    "metrics": {},
    "invalid_references": [],
    "evidence_basis": {
      "active_course_count": 8,
      "total_credits": 160,
      "credits_by_course_type": {"CORE": 100}
    }
  },
  "input_fingerprint": "sha256:...",
  "input_fingerprint_version": 1
}
```

`reference_comparison.status` is `NOT_CONFIGURED` when no applicable active
reference exists. No reference findings are generated in that case.

## 6. API

### Verification runs

| Method | Path | Access |
| --- | --- | --- |
| `POST` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/verification-runs` | `ADMIN`, `COMMITTEE_MEMBER`, `REVIEWER` |
| `GET` | same path | Authenticated |
| `GET` | `/api/v1/verification-runs/{run_id}` | Authenticated |
| `GET` | `/api/v1/verification-runs/{run_id}/findings` | Authenticated |
| `GET` | `/api/v1/verification-runs/{run_id}/report` | Authenticated |
| `GET` | `/api/v1/verification-findings/{finding_id}` | Authenticated |
| `PATCH` | `/api/v1/verification-findings/{finding_id}/review` | `ADMIN`, `COMMITTEE_MEMBER`, `REVIEWER` |

Run responses include `summary`, `input_fingerprint`, and `is_stale`.
The findings list supports `category` and `severity` filters. The report endpoint
groups filtered findings by `category`, `severity`, or `review_status` and
returns counts for all three dimensions.

### Governed references

| Method | Path | Access |
| --- | --- | --- |
| `GET` | `/api/v1/verification-references` | Authenticated |
| `POST` | `/api/v1/verification-references` | `ADMIN`, `COMMITTEE_MEMBER` |
| `PATCH` | `/api/v1/verification-references/{reference_id}` | `ADMIN`, `COMMITTEE_MEMBER` |

`GET` supports `program_id`, `reference_type`, and `include_inactive` filters.
Creation and update validate rules for the selected reference type. Duplicate
scope/code/version combinations return a conflict error. Creation and update are
audited with old and new values.

There is no delete endpoint; references are deactivated by setting
`status = INACTIVE`.

## 7. Run lifecycle and failure behavior

1. `POST` validates the curriculum/version pair and creates a
   `PROCESSING` run with `started_at` and a `CREATE` audit entry.
2. The snapshot is loaded and analyzed. Findings and references are attached in
   memory.
3. Findings and references are persisted; the summary is stored; the run becomes
   `COMPLETED`; one commit records the result.
4. If analysis raises, the run becomes `FAILED`, `completed_at` and
   `error_message` are stored, the failure is committed, and the error is
   re-raised (HTTP 500). Partial findings are not persisted.
5. If no findings are produced, the run completes with `result = PASSED`.

Runs are immutable. Re-running creates a new run; it does not update or delete
earlier runs or findings. Finding review decisions are audited separately and do
not change the run.

## 8. Visualization contract

`Frontend/src/components/verification-graph.tsx` renders the selected run's
curriculum map:

- courses are grouped by semester and active courses only;
- a node's outline color reflects the highest severity among findings that
  reference the course;
- prerequisite edges show the recorded status and use a dashed style for
  proposed rows;
- topic-overlap links are optional and styled by classification;
- selecting a node shows its findings, direct relationships, upstream chain, and
  dependent chain;
- an expandable table lists every active course with semester, credits, finding
  count, and highest severity as the accessible alternative;
- the page also shows stale-result state with a rerun action and a reference
  management panel.

## 9. Exclusions and limitations

- Topic analysis is lexical and deterministic; it does not use embeddings or
  LLMs and cannot detect conceptual overlap with no shared vocabulary.
- Industry skills depend on configured keyword quality.
- Institutional/program balance is evaluated only against governed references
  with explicit ranges; no built-in targets exist.
- PEO coverage is not inferred from PO mappings because no PO → PEO relationship
  is defined. PEOs are checked only for required pins in OBE references.
- Verification is advisory and never certifies accreditation compliance.
