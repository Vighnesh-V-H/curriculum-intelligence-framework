# AI-Powered Curriculum Intelligence & Verification Framework

An AI-powered framework for holistic analysis, verification, and quality assessment of academic curricula against Outcome-Based Education (OBE) principles, prerequisite dependencies, curriculum structure, accreditation expectations, and industry relevance.

## Contents

- [Project Overview](#project-overview)
- [Problem Statement](#problem-statement)
- [Objectives](#objectives)
- [Proposed Solution](#proposed-solution)
- [Core Capabilities](#core-capabilities)
- [System Architecture](#system-architecture)
- [Verification Engine](#verification-engine)
- [Verification Report](#verification-report)
- [Explainability and Human Review](#explainability-and-human-review)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Functional Requirements](#functional-requirements)
- [Non-Functional Requirements](#non-functional-requirements)
- [Scope](#scope)
- [Evaluation](#evaluation)
- [Repository Structure](#repository-structure)
- [Development Roadmap](#development-roadmap)
- [Project Status](#project-status)
- [Team and License](#team-and-license)

## Project Overview

Educational institutions continuously revise curricula to meet academic requirements, accreditation standards, evolving industry expectations, and OBE frameworks. Curriculum validation is often performed manually by committees reviewing courses, topics, Course Outcomes (COs), Program Outcomes (POs), Program Educational Objectives (PEOs), prerequisite relationships, credit distributions, and semester-wise sequencing.

This project proposes a framework that analyzes an entire degree-program curriculum as an interconnected system rather than evaluating courses independently. It represents curriculum information using a knowledge graph containing courses, topics, outcomes, semesters, prerequisites, corequisites, and outcome mappings. An NLP/LLM-based analysis engine extracts and interprets information from syllabus documents and compares it with declared curriculum structures.

The system identifies potential gaps, inconsistencies, redundancies, sequencing issues, and outcome-coverage problems and generates an interpretable Curriculum Verification Report.

## Problem Statement

Manual curriculum analysis makes it difficult to consistently identify:

- Missing or weak Program Outcome coverage
- Incorrect or inconsistent CO-PO mappings
- Courses appearing before their required prerequisites
- Missing foundational knowledge in prerequisite chains
- Excessive topic duplication or insufficient content progression
- Imbalanced credit distribution and semester-level outcome gaps
- Outdated or insufficiently represented industry competencies
- Potential misalignment with accreditation and OBE expectations

As curricula evolve, these interconnected issues become increasingly difficult to detect before curriculum review, accreditation, or implementation.

## Objectives

The proposed system aims to:

1. Ingest structured curriculum information and syllabus documents.
2. Extract courses, topics, outcomes, prerequisites, skills, and related entities.
3. Represent the curriculum and its relationships using a knowledge graph.
4. Analyze CO-PO mappings and program-level PO coverage.
5. Verify prerequisite chains and semester-wise course sequencing.
6. Detect topic overlap while distinguishing redundancy from legitimate progression.
7. Analyze credits, course distribution, dependencies, and curriculum structure.
8. Compare curriculum evidence with configured OBE, accreditation, and industry references.
9. Generate evidence-based findings, confidence scores, and recommendations.
10. Provide an interactive visual representation of the curriculum.
11. Support repeatable verification whenever curriculum data is updated.

## Proposed Solution

The framework combines deterministic rules, graph analysis, lexical text comparison, and governed reference data. LLM assistance is used to extract and draft curriculum content; verification findings remain deterministic, evidence-based, and subject to human review.

```text
Curriculum Documents
        |
        v
Document Ingestion and Validation
        |
        v
NLP / LLM Information Extraction
        |
        v
Structured Curriculum Representation
        |
        v
Curriculum Knowledge Graph
        |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
Outcome Analysis   Prerequisite Analysis   Structure Analysis
        |                  |                  |
        +------------------+------------------+
                           v
                  Verification Engine
                           |
                           v
          Findings, Recommendations, and Visual Map
```

### Example Extracted Course

```json
{
  "course_code": "CS301",
  "course_name": "Database Management Systems",
  "topics": [
    "Database Fundamentals",
    "ER Model",
    "Relational Model",
    "SQL",
    "Joins",
    "Nested Queries"
  ],
  "course_outcomes": [
    "Explain fundamental database concepts",
    "Design relational databases",
    "Develop SQL queries"
  ]
}
```

### Knowledge Graph Model

Major entities include Program, Course, Semester, Topic, Course Outcome, Program Outcome, Program Educational Objective, Skill, Accreditation Requirement, and Industry Competency.

```text
Course --------BELONGS_TO-------> Semester
Course --------COVERS-----------> Topic
Course --------HAS_OUTCOME------> Course Outcome
Course Outcome -CONTRIBUTES_TO--> Program Outcome
Course --------PREREQUISITE_OF-> Course
Course --------DEVELOPS---------> Skill
Program Outcome -SUPPORTS-------> Program Educational Objective
```

## Core Capabilities

### Document Ingestion and Extraction

The system will process curriculum structures, course syllabi, course descriptions, COs, POs, PEOs, CO-PO matrices, credit structures, semester plans, and prerequisite information. It will extract topics, modules, learning objectives, technologies, skills, competencies, and assessment-related information where available.

### CO-PO and PO Coverage Analysis

The framework compares declared CO-PO mappings with course content, Course Outcomes, topic-level evidence, and program-level coverage. It can identify weak mappings, insufficient evidence, concentrated outcome coverage, missing early exposure, and potential PO gaps.

### Prerequisite and Sequence Verification

Course dependencies are modeled as a directed graph. The system can identify invalid course references, missing prerequisite links, broken dependency chains, circular dependencies, and cases where a foundational course appears after a dependent course.

```text
Programming Fundamentals -> Data Structures -> Algorithms -> Machine Learning
```

These results are presented as potential issues requiring academic review, not as automatic academic judgments.

### Topic Overlap and Progression Analysis

Topic similarity is computed deterministically from course names, descriptions, syllabi, and active Course Outcomes. The analyzer compares topic profiles, course level, course-code discipline, semester position, and prerequisite reachability. Findings distinguish potential redundancy, legitimate prerequisite progression, unverified progression, and cross-discipline overlap. A legitimate prerequisite path suppresses redundancy findings. Semantic/embedding-based comparison remains a future extension.

### Curriculum Structure Analysis

The system analyzes semester-wise credits, core and elective distribution, course counts, semester sequence integrity, prerequisite depth, topic coverage, and course dependencies. Credit and distribution checks compare against configured institutional targets rather than built-in assumptions.

### Accreditation and Industry Alignment

Configured governed references support preliminary comparisons against OBE expectations, accreditation criteria, institutional credit/distribution targets, and industry competencies such as cloud computing, artificial intelligence, data engineering, cybersecurity, DevOps, and distributed systems. Rules, provenance, version, and severity are stored with each reference. These comparisons are advisory and do not claim official accreditation compliance.

## System Architecture

```text
                     Faculty / Curriculum Committee
                                  |
                                  v
                         React Curriculum UI
                                  |
                             REST / HTTP
                                  |
                                  v
                              FastAPI API
                                  |
             +--------------------+--------------------+
             |                    |                    |
             v                    v                    v
      Document Processing   Verification Engine   Reference Data
             |                    |
             v                    v
       NLP / LLM Layer     Rules and Graph Analysis
             |                    |
             +--------------------+
                                  v
                         Neo4j Curriculum Graph
                                  |
                                  v
                    Curriculum Verification Report
```

## Verification Engine

The engine combines deterministic rule-based, graph, lexical text, and governed-reference analysis. LLM assistance is used by document ingestion and draft generation, not as a verification decision-maker.

### Rule-Based Analysis

- Invalid semester or course references
- Duplicate course identifiers
- Credit inconsistencies and semester-sequence gaps
- Missing mappings and outcome coverage
- Invalid prerequisite references
- Cyclic prerequisite dependencies
- Institutional and program balance targets

### Graph-Based Analysis

- Prerequisite chains, roots, leaves, and longest paths
- Transitive redundant prerequisite edges
- PO coverage and outcome propagation
- Curriculum structure and progression

### Lexical Topic Analysis

- Topic profile extraction
- Course-content comparison
- Deterministic topic similarity and overlap detection
- Redundancy versus progression classification

### Governed Reference Analysis

- OBE outcome and mapping coverage targets
- Accreditation criterion requirements
- Industry skill keyword evidence
- Institutional credit, load, and distribution targets

## Verification Report

The report will organize findings by category and include:

- Issue and category
- Severity and confidence score
- Related courses, outcomes, or topics
- Evidence and explanation
- Recommendation
- Human-review requirement

Example categories include structural issues, outcome issues, dependency issues, content issues, industry alignment issues, and accreditation/OBE review areas.

## Explainability and Human Review

The framework is a decision-support system. It will not automatically approve or reject a curriculum, replace curriculum committees, claim official accreditation certification, or modify academic content without approval.

Each potential issue should explain why it was detected. For example:

```text
Potential Prerequisite Issue

Course: Machine Learning
Observed Structure: Machine Learning appears before Algorithms.
Evidence: Identified topics and outcomes indicate dependency on algorithmic concepts.
Confidence: 0.82
Recommendation: Review the prerequisite relationship and course sequencing.
```

The intended workflow is:

```text
AI Analysis -> Potential Finding -> Evidence and Explanation
            -> Faculty / Committee Review -> Accept, Reject, or Modify
```

## Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Uvicorn
- JWT bearer authentication

### AI and NLP

- Transformer-based models
- Embedding and semantic similarity models
- Large Language Models
- Python NLP ecosystem

### Knowledge Graph and Storage

- Neo4j
- Cypher Query Language
- Additional storage for application metadata where required

### Frontend and Documents

- Next.js (App Router)
- React.js
- TypeScript
- Tailwind CSS
- Graph visualization library
- PDF parsers, OCR, and document loaders as required

### Development

- Git and GitHub
- Postman
- VS Code
- Docker
- uv (Python dependency and environment management)

## Getting Started

### Backend

```text
cd backend
cp .env.example .env
# set DATABASE_URL, JWT_SECRET, and optionally BOOTSTRAP_ADMIN_PASSWORD
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`, with interactive
documentation at `http://localhost:8000/docs`. When
`BOOTSTRAP_ADMIN_PASSWORD` is set, the first start creates an administrator
account if it does not already exist. Backend logs are structured JSON on stdout;
set `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`) to adjust
verbosity. See [Backend Logging LLD](docs/lld/backend-logging.md) for the event
and privacy policy.

### Frontend

```text
cd Frontend
cp .env.example .env.local
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` and signs in against the FastAPI
API.

### Optional Neo4j knowledge graph

The **Curricula → Knowledge graph** tab reads a version-scoped projection from
Neo4j. Relational curriculum features work without Neo4j; the graph tab shows
setup guidance and the graph API returns `503 graph_unavailable` until a
connection is configured.

With Docker installed, start a development instance:

```text
docker compose -f scripts/neo4j-compose.yml up -d
```

Then add the connection settings to `backend/.env` and restart the API:

```text
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=curriculum-dev-password
NEO4J_DATABASE=neo4j
```

Open the curriculum version and use **Rebuild projection** in the Knowledge
graph tab. Keep projections current while the API is running:

```text
cd backend
uv run python -m app.workers.graph_projection
```

### Development servers (Windows)

To stop any previously running dev servers and start both together in separate
console windows (the backend binds to `127.0.0.1`):

The script uses port `8000` when available; if a stale listener holds it, it
selects the next available port and configures the frontend to call that API.

```text
scripts\dev.bat
```

The backend and frontend consoles stay open so logs are visible; the frontend
must be opened via `http://localhost:3000`.

## Functional Requirements

- **FR1 - Curriculum Ingestion:** Accept authorized curriculum documents and structured data.
- **FR2 - Information Extraction:** Extract courses, topics, outcomes, prerequisites, skills, and related entities.
- **FR3 - Knowledge Graph Construction:** Build and maintain the curriculum graph.
- **FR4 - Outcome Mapping Analysis:** Analyze CO-PO and PO-level coverage.
- **FR5 - Prerequisite Verification:** Identify prerequisite and sequencing inconsistencies.
- **FR6 - Topic Similarity Analysis:** Identify potentially duplicated or overlapping content.
- **FR7 - Structure Analysis:** Analyze credits, semesters, dependencies, and progression.
- **FR8 - Accreditation Analysis:** Compare evidence with configured OBE and accreditation criteria.
- **FR9 - Industry Analysis:** Compare competencies with a maintained industry reference dataset.
- **FR10 - Verification Report:** Generate findings, evidence, severity, and recommendations.
- **FR11 - Visualization:** Provide an interactive graph-based curriculum view.
- **FR12 - Curriculum Revision:** Reprocess updated curriculum data through the pipeline.

## Non-Functional Requirements

- **Accuracy:** Clearly identify uncertain findings and evaluate extraction quality.
- **Explainability:** Provide evidence and reasoning for detected issues.
- **Scalability:** Support complete programs containing multiple semesters and hundreds of entities.
- **Maintainability:** Keep ingestion, extraction, graph, and verification modules independent where practical.
- **Extensibility:** Support additional standards, domains, programs, and industry datasets.
- **Security:** Handle curriculum documents and institutional information securely.
- **Performance:** Optimize frequently used verification operations and graph queries.

## Scope

The initial implementation focuses on a complete academic degree program and its curriculum structure. It primarily analyzes courses, semesters, credits, topics, COs, POs, PEOs, prerequisites, CO-PO mappings, curriculum dependencies, and topic relationships.

### Out of Scope

- Automatic curriculum approval or rejection
- Replacement of academic experts or curriculum committees
- Official accreditation certification
- Final academic decisions without human review
- Automatic curriculum modification
- Treating LLM suggestions as authoritative academic decisions

## Evaluation

The project will be evaluated using technical and domain-specific metrics:

- Information extraction precision, recall, and F1-score
- Semantic similarity accuracy and false-positive analysis
- CO-PO consistency and PO coverage accuracy
- Prerequisite detection accuracy and graph consistency
- Expert agreement and faculty validation
- API response time, document processing time, and graph query performance
- Usability and report interpretability

## Repository Structure

```text
curriculum-intelligence-framework/
|
|-- backend/
|   |-- alembic/
|   |   |-- sql/
|   |   `-- versions/
|   |-- app/
|   |   |-- api/
|   |   |-- core/
|   |   |-- db/
|   |   |-- repositories/
|   |   |-- schemas/
|   |   |-- services/
|   |   `-- main.py
|   |-- tests/
|   |-- alembic.ini
|   |-- pyproject.toml
|   `-- uv.lock
|
|-- Frontend/
|   |-- src/
|   |   |-- app/
|   |   `-- lib/
|   |-- public/
|   |-- package.json
|   `-- README.md
|
|-- data/
|   |-- curriculum/
|   |-- reference/
|   `-- sample/
|
|-- docs/
|-- notebooks/
|-- scripts/
|-- .gitignore
|-- LICENSE
`-- README.md
```

## Development Roadmap

1. Requirement analysis and definition of curriculum entities.
2. Curriculum schema and Neo4j graph model.
3. Document ingestion, preprocessing, extraction, and validation.
4. Knowledge graph construction and graph queries.
5. Structural, prerequisite, CO-PO, PO coverage, and topic-overlap verification.
6. Semantic similarity and LLM-assisted evidence generation.
7. Accreditation and industry reference analysis.
8. React dashboard, graph visualization, and course details.
9. Unit, integration, NLP, graph, end-to-end, and expert validation testing.
10. Containerization, deployment, and documentation.

## Project Status

**Current Status:** Initial Development

### Completed

- [x] Project problem identification
- [x] Project scope definition
- [x] Initial system objectives
- [x] Initial architecture planning
- [x] Curriculum relational data model and PostgreSQL schema (`docs/lld/database-schema.md`)
- [x] FastAPI backend foundation with layered architecture
- [x] FR-01 user authentication, JWT authorization, and role management (`docs/lld/authentication.md`)
- [x] FR-02 create curriculum with initial draft version and academic structure
- [x] FR-03 update curriculum, with published versions locked for editing
- [x] FR-04 curriculum versioning, status workflow, and version comparison
- [x] FR-05 add course to an editable curriculum version
- [x] FR-06 update course details and semester allocation
- [x] FR-07 remove course with soft-delete history and dependency check
  (`docs/lld/curriculum-management.md`)
- [x] FR-08 Program Outcome management with version workflow and audit trail
- [x] FR-09 Program Educational Objective management with version workflow
  (`docs/lld/program-outcomes.md`)
- [x] FR-10 Course Outcome management and CO-PO mapping with review workflow
  (`docs/lld/co-po-mapping.md`)
- [x] FR-11 Prerequisite management with cycle prevention and review workflow
  (`docs/lld/prerequisite-management.md`)
- [x] FR-12 Prerequisite verification engine with runs, findings, and audit trail
  (`docs/lld/prerequisite-verification.md`)
- [x] FR-13 document upload, extraction, LLM analysis, retry, and draft workflow;
  the draft studio also accepts a topic brief with optional reference documents,
  saves the generated draft automatically as curriculum version 1.0 in DRAFT
  status, and lists all saved drafts
  (`docs/lld/document-processing.md`, `docs/lld/curriculum-management.md`)
- [x] FR-14 curriculum verification: prerequisite chains and sequencing, semester/credit
  distribution, topic overlap versus progression, outcome coverage, governed
  OBE/accreditation/industry/institutional comparison, stale-run detection, finding
  review, reporting, and an interactive severity-aware verification map
  (`docs/lld/curriculum-verification.md`)
- [x] Neo4j graph projection, transactional outbox worker, and frontend knowledge graph explorer
  (`docs/lld/knowledge-graph.md`)
- [x] Next.js authenticated workspace covering curriculum, outcomes, verification, documents,
  administration, comparison, and accessible graph exploration

### In Progress

- [ ] Evaluation datasets and extraction/analysis quality measures
- [ ] Semantic/embedding-based topic and skill matching
- [ ] Browser-level end-to-end tests and domain expert validation

### Planned

- [ ] Production deployment, containerization, and operational documentation

## Team and License

This is a final-year major project developed as part of the B.Tech Computer Science and Engineering program.

The project is developed for academic and research purposes. Licensing terms will be finalized as the project progresses.
