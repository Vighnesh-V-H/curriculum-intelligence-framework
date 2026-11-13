"use client";

import { useMemo, useRef, useState } from "react";
import type {
  Course,
  CourseOutcome,
  Mapping,
  Outcome,
  Prerequisite,
} from "@/lib/api";

type Semester = { id: string; semester_number: number; name: string | null };
type MapNode = {
  id: string;
  kind: "Course" | "Course outcome" | "Program outcome" | "PEO";
  title: string;
  subtitle: string;
  x: number;
  y: number;
  width: number;
  height: number;
  status?: string;
};
type MapEdge = {
  id: string;
  source: string;
  target: string;
  type: "prerequisite" | "outcome" | "mapping";
  status: string;
};

type Props = {
  courses: Course[];
  semesters: Semester[];
  prerequisites: Prerequisite[];
  courseOutcomes: Record<string, CourseOutcome[]>;
  mappings: Mapping[];
  programOutcomes: Outcome[];
  peos: Outcome[];
};

const COURSE_W = 156;
const CO_W = 144;
const OUTCOME_W = 156;
const ROW_H = 76;
const COLUMN_GAP = 34;
const TOP = 64;

function statusClass(status: string | undefined) {
  return status?.toLowerCase().replaceAll("_", "-") ?? "";
}

export function CurriculumKnowledgeMap({
  courses,
  semesters,
  prerequisites,
  courseOutcomes,
  mappings,
  programOutcomes,
  peos,
}: Props) {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [zoom, setZoom] = useState(0.72);
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const dragged = useRef(false);
  const model = useMemo(() => {
    const orderedSemesters = [...semesters].sort(
      (a, b) => a.semester_number - b.semester_number,
    );
    const coursePositions = new Map<string, number>();
    const nodes: MapNode[] = [];
    const semesterX = new Map<number, number>();
    const coursesBySemester = orderedSemesters.map((semester, index) => {
      semesterX.set(semester.semester_number, 40 + index * (COURSE_W + COLUMN_GAP));
      return {
        semester,
        courses: courses.filter((course) => course.semester_number === semester.semester_number),
      };
    });

    let courseRow = 0;
    for (const { semester, courses: semesterCourses } of coursesBySemester) {
      const x = semesterX.get(semester.semester_number) ?? 40;
      semesterCourses.forEach((course, index) => {
        const y = TOP + (courseRow + index) * ROW_H;
        coursePositions.set(course.id, y);
        nodes.push({
          id: course.id,
          kind: "Course",
          title: course.course_code,
          subtitle: course.course_name,
          x,
          y,
          width: COURSE_W,
          height: 54,
          status: course.status,
        });
      });
      courseRow += Math.max(semesterCourses.length, 1) + 0.65;
    }

    const coX = 40 + orderedSemesters.length * (COURSE_W + COLUMN_GAP);
    const coPositions = new Map<string, number>();
    const allCourseOutcomes = courses.flatMap((course) =>
      (courseOutcomes[course.id] ?? []).map((co) => ({ course, co })),
    );
    const perCourseIndex = new Map<string, number>();
    allCourseOutcomes.forEach(({ course, co }) => {
      const index = perCourseIndex.get(course.id) ?? 0;
      perCourseIndex.set(course.id, index + 1);
      const y = (coursePositions.get(course.id) ?? TOP) + index * 48;
      coPositions.set(co.id, y);
      nodes.push({
        id: co.id,
        kind: "Course outcome",
        title: co.co_code,
        subtitle: co.description,
        x: coX,
        y,
        width: CO_W,
        height: 40,
        status: co.status,
      });
    });

    const poX = coX + CO_W + COLUMN_GAP;
    const poPositions = new Map<string, number>();
    programOutcomes.forEach((po, index) => {
      const y = TOP + index * ROW_H;
      poPositions.set(po.id, y);
      nodes.push({
        id: po.id,
        kind: "Program outcome",
        title: po.po_code ?? "PO",
        subtitle: po.current_version?.description ?? "No current description",
        x: poX,
        y,
        width: OUTCOME_W,
        height: 54,
        status: po.status,
      });
    });
    const peoStart = TOP + Math.max(programOutcomes.length, 1) * ROW_H + 38;
    peos.forEach((peo, index) => {
      const y = peoStart + index * ROW_H;
      nodes.push({
        id: peo.id,
        kind: "PEO",
        title: peo.peo_code ?? "PEO",
        subtitle: peo.current_version?.description ?? "No current description",
        x: poX,
        y,
        width: OUTCOME_W,
        height: 54,
        status: peo.status,
      });
    });

    const edges: MapEdge[] = [];
    prerequisites.forEach((item) => {
      if (coursePositions.has(item.prerequisite_course_id) && coursePositions.has(item.target_course_id)) {
        edges.push({ id: item.id, source: item.prerequisite_course_id, target: item.target_course_id, type: "prerequisite", status: item.status });
      }
    });
    allCourseOutcomes.forEach(({ course, co }) => {
      edges.push({ id: `outcome:${co.id}`, source: course.id, target: co.id, type: "outcome", status: co.status });
    });
    mappings.forEach((mapping) => {
      if (coPositions.has(mapping.course_outcome_id) && poPositions.has(mapping.program_outcome_id)) {
        edges.push({ id: mapping.id, source: mapping.course_outcome_id, target: mapping.program_outcome_id, type: "mapping", status: mapping.current_version?.status ?? mapping.status });
      }
    });

    const byId = new Map(nodes.map((node) => [node.id, node]));
    const width = Math.max(760, poX + OUTCOME_W + 40);
    const height = Math.max(
      220,
      ...nodes.map((node) => node.y + node.height + 34),
    );
    return { nodes, edges, byId, width, height, coursesBySemester, semesterX };
  }, [courses, semesters, prerequisites, courseOutcomes, mappings, programOutcomes, peos]);

  const normalizedSearch = search.trim().toLocaleLowerCase();
  const matchingIds = normalizedSearch
    ? new Set(
        model.nodes
          .filter((node) => `${node.kind} ${node.title} ${node.subtitle}`.toLocaleLowerCase().includes(normalizedSearch))
          .map((node) => node.id),
      )
    : null;
  const selected = model.byId.get(selectedId);

  const nodeColumn = (kind: MapNode["kind"]) => model.nodes.some((node) => node.kind === kind);
  const courseCount = courses.length;
  const outcomeCount = Object.values(courseOutcomes).reduce((sum, rows) => sum + rows.length, 0);

  return (
    <div className="curriculum-map">
      <header className="curriculum-map__header">
        <div>
          <h3>Curriculum relationship map</h3>
          <p>Built from the selected version’s curriculum data. It works independently of the Neo4j projection.</p>
        </div>
        <div className="curriculum-map__controls">
          <label className="curriculum-map__search">
            <span className="sr-only">Search map nodes</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search courses and outcomes" />
          </label>
          <div className="curriculum-map__zoom" aria-label="Map zoom controls">
            <button type="button" aria-label="Zoom out" disabled={zoom <= 0.4} onClick={() => setZoom((value) => Math.max(0.4, Math.round((value - 0.15) * 100) / 100))}>−</button>
            <output aria-live="polite">{Math.round(zoom * 100)}%</output>
            <button type="button" aria-label="Zoom in" disabled={zoom >= 1.8} onClick={() => setZoom((value) => Math.min(1.8, Math.round((value + 0.15) * 100) / 100))}>+</button>
            <button type="button" className="curriculum-map__fit" onClick={() => { setZoom(0.72); const viewport = document.querySelector<HTMLElement>(".curriculum-map__viewport"); if (viewport) { viewport.scrollTo({ left: 0, top: 0, behavior: "smooth" }); } }}>Reset view</button>
          </div>
        </div>
      </header>

      {!courses.length ? (
        <p className="academic-empty">This version has no courses to map yet.</p>
      ) : (
        <>
          <div className="curriculum-map__legend" aria-label="Map relationship legend">
            <span><i className="is-prerequisite" /> Prerequisite</span>
            <span><i className="is-outcome" /> Course outcome</span>
            <span><i className="is-mapping" /> CO–PO mapping</span>
            <span className="curriculum-map__counts">{courseCount} courses · {outcomeCount} course outcomes · {programOutcomes.length} POs · {peos.length} PEOs</span>
          </div>
          <div
            className={`curriculum-map__viewport${isPanning ? " is-panning" : ""}`}
            tabIndex={0}
            aria-label="Scrollable curriculum relationship map. Drag to pan."
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              const viewport = event.currentTarget;
              panStart.current = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
              dragged.current = false;
              viewport.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              const start = panStart.current;
              if (!start) return;
              const dx = event.clientX - start.x;
              const dy = event.clientY - start.y;
              if (Math.abs(dx) + Math.abs(dy) > 4) {
                dragged.current = true;
                setIsPanning(true);
                event.currentTarget.scrollLeft = start.left - dx;
                event.currentTarget.scrollTop = start.top - dy;
              }
            }}
            onPointerUp={() => {
              panStart.current = null;
              setIsPanning(false);
              if (dragged.current) window.setTimeout(() => { dragged.current = false; }, 0);
            }}
            onPointerCancel={() => { panStart.current = null; setIsPanning(false); dragged.current = false; }}
          >
            <svg role="img" aria-label="Curriculum courses, course outcomes, and program outcome relationships" viewBox={`0 0 ${model.width} ${model.height}`} width={Math.round(model.width * zoom)} height={Math.round(model.height * zoom)}>
              <defs>
                <marker id="curriculum-map-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7Z" /></marker>
              </defs>
              {model.coursesBySemester.map(({ semester }, index) => {
                const x = model.semesterX.get(semester.semester_number) ?? 40;
                return <g key={semester.id}>
                  <text className="curriculum-map__column-label" x={x} y={30}>{semester.name ?? `Semester ${semester.semester_number}`}</text>
                  <text className="curriculum-map__column-count" x={x} y={46}>{courses.filter((course) => course.semester_number === semester.semester_number).length} courses</text>
                  {index > 0 ? <line className="curriculum-map__separator" x1={x - COLUMN_GAP / 2} x2={x - COLUMN_GAP / 2} y1={18} y2={model.height - 18} /> : null}
                </g>;
              })}
              {nodeColumn("Course outcome") ? <text className="curriculum-map__column-label" x={40 + model.coursesBySemester.length * (COURSE_W + COLUMN_GAP)} y={30}>Course outcomes</text> : null}
              {nodeColumn("Program outcome") ? <text className="curriculum-map__column-label" x={40 + model.coursesBySemester.length * (COURSE_W + COLUMN_GAP) + CO_W + COLUMN_GAP} y={30}>Program outcomes</text> : null}
              {model.edges.map((edge) => {
                const from = model.byId.get(edge.source);
                const to = model.byId.get(edge.target);
                if (!from || !to) return null;
                const focused = !selectedId || edge.source === selectedId || edge.target === selectedId;
                const matches = !matchingIds || matchingIds.has(edge.source) || matchingIds.has(edge.target);
                const fromX = from.x + from.width;
                const fromY = from.y + from.height / 2;
                const toX = to.x;
                const toY = to.y + to.height / 2;
                const curve = Math.max(32, (toX - fromX) * 0.42);
                return <path key={edge.id} className={`curriculum-map__edge is-${edge.type} is-${statusClass(edge.status)}${focused && matches ? "" : " is-dimmed"}`} d={`M ${fromX} ${fromY} C ${fromX + curve} ${fromY}, ${toX - curve} ${toY}, ${toX} ${toY}`} markerEnd="url(#curriculum-map-arrow)"><title>{edge.type.replaceAll("-", " ")} · {edge.status.toLowerCase()}</title></path>;
              })}
              {model.nodes.map((node) => {
                const matched = !matchingIds || matchingIds.has(node.id);
                const connected = !selectedId || node.id === selectedId || model.edges.some((edge) => (edge.source === selectedId && edge.target === node.id) || (edge.target === selectedId && edge.source === node.id));
                return <g key={`${node.kind}:${node.id}`} transform={`translate(${node.x} ${node.y})`} tabIndex={0} role="button" aria-pressed={node.id === selectedId} aria-label={`${node.kind}: ${node.title}. ${node.subtitle}`} className={`curriculum-map__node is-${node.kind.toLowerCase().replaceAll(" ", "-")}${node.id === selectedId ? " is-selected" : ""}${matched && connected ? "" : " is-dimmed"}`} onClick={() => { if (dragged.current) { dragged.current = false; return; } setSelectedId(node.id); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(node.id); } }}>
                  <rect width={node.width} height={node.height} rx="5" />
                  <text className="curriculum-map__node-title" x="10" y={node.height === 40 ? 17 : 20}>{node.title}</text>
                  <text className="curriculum-map__node-subtitle" x="10" y={node.height === 40 ? 31 : 38}>{node.subtitle.length > 28 ? `${node.subtitle.slice(0, 27)}…` : node.subtitle}</text>
                  <title>{node.kind} · {node.title} · {node.subtitle}{node.status ? ` · ${node.status}` : ""}</title>
                </g>;
              })}
            </svg>
          </div>
          <div className="curriculum-map__below">
            <section className="curriculum-map__selection" aria-live="polite">
              {selected ? <><span>{selected.kind}</span><h4>{selected.title}</h4><p>{selected.subtitle}</p>{selected.status ? <small>Status: {selected.status.toLowerCase().replaceAll("_", " ")}</small> : null}</> : <p>Select a node to inspect it. Search dims non-matching nodes.</p>}
            </section>
            <details className="curriculum-map__table">
              <summary>Accessible relationship list <span>{model.edges.length} links</span></summary>
              {model.edges.length ? <div className="curriculum-map__table-scroll"><table><thead><tr><th>From</th><th>Relationship</th><th>To</th><th>Status</th></tr></thead><tbody>{model.edges.map((edge) => { const from = model.byId.get(edge.source); const to = model.byId.get(edge.target); return from && to ? <tr key={edge.id}><td>{from.title}</td><td>{edge.type.replaceAll("-", " ")}</td><td>{to.title}</td><td>{edge.status.toLowerCase().replaceAll("_", " ")}</td></tr> : null; })}</tbody></table></div> : <p>No relationships are recorded for this version.</p>}
            </details>
          </div>
        </>
      )}
    </div>
  );
}
