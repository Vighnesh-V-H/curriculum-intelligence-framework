from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
from xml.sax.saxutils import escape
import re

src = Path('Project_Presentation_Template.pptx')
out = Path('Curriculum_Intelligence_Project_Presentation.pptx')
# Fill the Project Presentation template in place: all slide layouts, theme, masters,
# and existing visual styling are retained.
replacements = {
 1: {'[Project ':'AI-Powered Curriculum Intelligence & Verification Framework', 'title]':'', 'Phase-1 (about 70% complete)':'Phase-1: Core workflow implemented'},
 2: {'The problem in one or two sentences.':'Manual reviews miss cross-course gaps, prerequisite errors, and weak outcome coverage.', 'Who uses it and why it matters.':'Faculty and curriculum committees need evidence to improve curricula and support OBE review.', 'What success looks like (one measurable outcome).':'A repeatable, evidence-linked verification report across curriculum structure and outcomes.', 'Gap 1: [ ]':'Gap 1: Course-by-course reviews miss curriculum-wide relationships.', 'Gap 2: [ ]':'Gap 2: Findings are difficult to trace to evidence or review consistently.', 'The gap my module addresses: [ ]':'This framework combines graph analysis, deterministic checks, and explainable human review.'},
 3: {'Paper (author, year)':'Related work / approach', 'Approach':'Contribution to this project', 'Strength':'Strength', 'Limitation':'Limitation', '[ ]':'OBE / curriculum analytics',},
 4: {'[Functional]':'Functional: versioned curriculum management', '[Non-functional]':'Functional: document-to-draft workflow', '[High]':'High: outcome and prerequisite analysis',}, 
 5: {'[Insert system architecture diagram]':'Documents & curriculum → FastAPI services → deterministic verification + graph analysis → reports & interactive UI', 'Key choice 1 and the alternative I rejected.':'PostgreSQL is the source of truth; Neo4j is a version-scoped graph projection, not a competing source.', 'Key choice 2 and why.':'Rules and evidence drive findings; LLM assistance supports extraction/drafting, not academic decisions.'},
 6: {'[Flowchart: main logic]':'Ingest → validate → extract → review/edit draft → save curriculum → run verification', '[UML: class / sequence / use case]':'Entities: Program, Curriculum, Version, Course, CO, PO/PEO, prerequisite, finding', '[DFD: level 0 and 1]':'Data flow: documents and structured data → relational store / graph projection → findings and report', 'Each design element traces back to a requirement ID (R1, R2, ...).':'Traceability: R1–R4 map to versioned APIs, service analyses, persistence, and review UI.'},
 7: {'target about 30%  |  actual: [ ]%':'Core foundations: implemented', 'target about 55%  |  actual: [ ]%':'Analysis and workflow: implemented', 'target about 70%  |  actual: [ ]%':'Phase-1 baseline: implemented', 'Features working at each checkpoint: [ ]':'Working: curriculum/version management, document-to-draft flow, verification reports, review actions, visual exploration.'},
 8: {'[Screenshot: feature 1]':'Curriculum workspace: versions, courses, outcomes and mappings', '[Screenshot: feature 2]':'Verification: severity, evidence, confidence and recommendations', '[Screenshot: feature 3]':'Interactive prerequisite / curriculum map with accessible table', 'Main file / function, key logic.':'FastAPI service layer runs version-scoped structure, outcome, prerequisite, topic, and reference checks.', 'Before / after, in one line.':'Before: fragmented manual checks. After: repeatable findings with evidence and human review.'},
 9: {'[ ]':'Backend tests cover APIs, security, analysis, graph projection, and end-to-end workflows.', 'testcases designed':'Automated test coverage', 'passed':'Implemented', 'failed / fixed':'Regression cases included', 'T1':'T1 Structure', 'T2 (boundary)':'T2 Boundary', 'T3 (negative)':'T3 Negative', 'Input':'Input', 'Expected':'Expected', 'Actual':'Observed behavior', 'Result':'Status'},
 10: {'[Before screenshot]':'Relational curriculum records', '[After screenshot]':'Neo4j projection and freshness status', 'Symptom, root cause (one line), fix.':'Risk: graph can lag after relational writes. Fix: transactional outbox, retrying projection worker, and freshness metadata.', 'How the modules connect.':'Document ingestion creates editable drafts; saved versions feed graph projection and verification.', 'Integration bugs I met.':'Projection lag, stale verification runs, invalid document inputs, and version consistency.', 'How I resolved them.':'Retries and freshness tracking; input validation; fingerprint-based stale-run detection; integration tests.'},
 11: {'3 to 5 bullets with week numbers.':'Built curriculum and verification workflows; document-to-draft generation; graph projection; reports and review UI.', 'Team members and what they did.':'Project team: [add member names and contributions]', 'Pending work (about 30%)':'Evaluation, browser E2E, production deployment', 'Approach':'Work item', 'Target week':'Next step'},
 12: {'What I tried, what worked, and what I would do differently.':'Key learning: make findings traceable, version-aware, and advisory; validate with labelled data and domain experts next.', '[GitHub repository link]':'[GitHub repository link]'},
}

def alter(xml, mapping):
    # Replace only text element contents; retain the original XML structure and formatting.
    for old, new in mapping.items():
        old_xml, new_xml = escape(old), escape(new)
        xml = xml.replace('>' + old_xml + '<', '>' + new_xml + '<')
    return xml

with ZipFile(src) as zin, ZipFile(out, 'w', ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        m = re.fullmatch(r'ppt/slides/slide(\d+)\.xml', item.filename)
        if m:
            n = int(m.group(1))
            if n in replacements:
                data = alter(data.decode('utf-8'), replacements[n]).encode('utf-8')
        zout.writestr(item, data)
print(out)
