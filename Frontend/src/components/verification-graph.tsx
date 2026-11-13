"use client";

import { useMemo, useState } from "react";

import type {
  Course,
  Prerequisite,
  VerificationFinding,
  VerificationRunSummary,
} from "@/lib/api";

type TopicOverlap = NonNullable<
  NonNullable<VerificationRunSummary["topic_overlap"]>["top_overlaps"]
>[number];

type Props = {
  courses: Course[];
  prerequisites: Prerequisite[];
  findings: VerificationFinding[];
  topicOverlaps?: TopicOverlap[];
};

const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 5,
  HIGH: 4,
  MEDIUM: 3,
  LOW: 2,
  INFO: 1,
};

const SEVERITY_LABEL: Record<string, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
  INFO: "Info",
};

function courseFindings(courseId: string, findings: VerificationFinding[]) {
  return findings.filter((finding) =>
    finding.references.some(
      (reference) => reference.entity_type === "COURSE" && reference.entity_id === courseId,
    ),
  );
}

function highestSeverity(findings: VerificationFinding[]): string | null {
  let highest: string | null = null;
  for (const finding of findings) {
    if (!highest || (SEVERITY_RANK[finding.severity] ?? 0) > (SEVERITY_RANK[highest] ?? 0)) {
      highest = finding.severity;
    }
  }
  return highest;
}

function reachable(
  startId: string,
  edges: Prerequisite[],
  direction: "upstream" | "downstream",
  courseById: Map<string, Course>,
): string[] {
  const seen = new Set<string>();
  const queue = [startId];
  while (queue.length) {
    const current = queue.shift()!;
    for (const edge of edges) {
      const next = direction === "upstream"
        ? edge.target_course_id === current
          ? edge.prerequisite_course_id
          : null
        : edge.prerequisite_course_id === current
          ? edge.target_course_id
          : null;
      if (next && next !== startId && !seen.has(next)) {
        seen.add(next);
        queue.push(next);
      }
    }
  }
  return Array.from(seen)
    .map((id) => courseById.get(id)?.course_code ?? id)
    .sort();
}

export function VerificationGraph({ courses, prerequisites, findings, topicOverlaps = [] }: Props) {
  const activeCourses = useMemo(
    () => courses.filter((course) => course.status === "ACTIVE"),
    [courses],
  );
  const activePrerequisites = useMemo(
    () => prerequisites.filter((item) => item.status !== "REJECTED"),
    [prerequisites],
  );
  const [selectedId, setSelectedId] = useState(activeCourses[0]?.id ?? "");
  const [showTopics, setShowTopics] = useState(topicOverlaps.length > 0);
  const selected = activeCourses.find((course) => course.id === selectedId) ?? null;
  const courseById = useMemo(
    () => new Map(activeCourses.map((course) => [course.id, course])),
    [activeCourses],
  );
  const courseByCode = useMemo(
    () => new Map(activeCourses.map((course) => [course.course_code, course])),
    [activeCourses],
  );

  const semesters = useMemo(() => {
    const numbers = Array.from(new Set(activeCourses.map((course) => course.semester_number)))
      .sort((left, right) => left - right);
    return numbers.map((number) => ({
      number,
      courses: activeCourses
        .filter((course) => course.semester_number === number)
        .sort((left, right) => left.course_code.localeCompare(right.course_code)),
    }));
  }, [activeCourses]);

  const positions = useMemo(() => {
    const result = new Map<string, { x: number; y: number }>();
    semesters.forEach((semester, semesterIndex) => {
      semester.courses.forEach((course, courseIndex) => {
        result.set(course.id, {
          x: 122 + semesterIndex * 232,
          y: 74 + courseIndex * 78,
        });
      });
    });
    return result;
  }, [semesters]);

  const width = Math.max(700, semesters.length * 232 + 130);
  const height = Math.max(
    240,
    Math.max(...semesters.map((semester) => semester.courses.length), 1) * 78 + 120,
  );

  const selectedFindings = selected ? courseFindings(selected.id, findings) : [];
  const selectedSeverity = highestSeverity(selectedFindings);
  const incoming = selected
    ? activePrerequisites.filter((item) => item.target_course_id === selected.id)
    : [];
  const outgoing = selected
    ? activePrerequisites.filter((item) => item.prerequisite_course_id === selected.id)
    : [];
  const upstream = selected
    ? reachable(selected.id, activePrerequisites, "upstream", courseById)
    : [];
  const downstream = selected
    ? reachable(selected.id, activePrerequisites, "downstream", courseById)
    : [];

  const topicLinks = useMemo(
    () => topicOverlaps.flatMap((overlap) => {
      const left = courseByCode.get(overlap.course_a);
      const right = courseByCode.get(overlap.course_b);
      if (!left || !right) return [];
      const from = positions.get(left.id);
      const to = positions.get(right.id);
      if (!from || !to) return [];
      return [{ overlap, from, to }];
    }),
    [courseByCode, positions, topicOverlaps],
  );

  if (!activeCourses.length) {
    return <p className="verification-graph__empty">No active courses to visualize.</p>;
  }

  return (
    <div className="verification-graph">
      <div className="verification-graph__toolbar">
        <div className="verification-graph__legend" aria-label="Finding severity legend">
          {["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((severity) => (
            <span key={severity}>
              <i className={`verification-graph__swatch verification-graph__swatch--${severity.toLowerCase()}`} />
              {SEVERITY_LABEL[severity]}
            </span>
          ))}
          <span><i className="verification-graph__swatch verification-graph__swatch--clear" />No finding</span>
        </div>
        {topicOverlaps.length ? (
          <label className="verification-graph__toggle">
            <input
              type="checkbox"
              checked={showTopics}
              onChange={(event) => setShowTopics(event.target.checked)}
            />
            Show topic overlaps
          </label>
        ) : null}
      </div>

      <div className="verification-graph__canvas">
        <svg
          role="img"
          aria-label="Verification-aware curriculum map grouped by semester"
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height={height}
        >
          <defs>
            <marker id="verification-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="currentColor" />
            </marker>
          </defs>
          {semesters.map((semester, index) => (
            <text
              key={semester.number}
              x={122 + index * 232}
              y={28}
              textAnchor="middle"
              className="verification-graph__semester"
            >
              Semester {semester.number}
            </text>
          ))}
          {activePrerequisites.map((edge) => {
            const from = positions.get(edge.prerequisite_course_id);
            const to = positions.get(edge.target_course_id);
            if (!from || !to) return null;
            return (
              <path
                key={edge.id}
                d={`M ${from.x} ${from.y} C ${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x} ${to.y}`}
                className={`verification-graph__edge verification-graph__edge--${edge.status.toLowerCase()}`}
                markerEnd="url(#verification-arrow)"
              />
            );
          })}
          {showTopics ? topicLinks.map(({ overlap, from, to }) => (
            <line
              key={`${overlap.course_a}-${overlap.course_b}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              className={`verification-graph__topic verification-graph__topic--${overlap.classification.toLowerCase()}`}
            >
              <title>
                {overlap.course_a} and {overlap.course_b}: {overlap.classification.replaceAll("_", " ").toLowerCase()} ({Math.round(overlap.score * 100)}%)
              </title>
            </line>
          )) : null}
          {semesters.flatMap((semester) => semester.courses.map((course) => {
            const position = positions.get(course.id);
            if (!position) return null;
            const matched = courseFindings(course.id, findings);
            const severity = highestSeverity(matched);
            const isSelected = course.id === selectedId;
            return (
              <g
                key={course.id}
                transform={`translate(${position.x}, ${position.y})`}
                tabIndex={0}
                role="button"
                aria-pressed={isSelected}
                aria-label={`${course.course_code} ${course.course_name}, semester ${course.semester_number}, ${matched.length} verification finding${matched.length === 1 ? "" : "s"}`}
                className={[
                  "verification-graph__node",
                  isSelected ? "is-selected" : "",
                  severity ? `verification-graph__node--${severity.toLowerCase()}` : "",
                ].filter(Boolean).join(" ")}
                onClick={() => setSelectedId(course.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedId(course.id);
                  }
                }}
              >
                <circle r="25" />
                <text y="4" textAnchor="middle">{course.course_code}</text>
                <title>{course.course_code} · {course.course_name}</title>
              </g>
            );
          }))}
        </svg>
        <p className="verification-graph__hint">
          Node colour reflects the highest-severity finding linked to the course. Select a
          node to inspect evidence, prerequisites, and dependencies.
        </p>
      </div>

      <div className="verification-graph__detail">
        {selected ? (
          <>
            <div className="verification-graph__detail-heading">
              <div>
                <h3>{selected.course_code} · {selected.course_name}</h3>
                <p>
                  {selected.course_type_name} · {selected.credits} credits · Semester{" "}
                  {selected.semester_number}
                </p>
              </div>
              <span className={`verification-graph__severity verification-graph__severity--${(selectedSeverity ?? "clear").toLowerCase()}`}>
                {selectedSeverity ? `${SEVERITY_LABEL[selectedSeverity]} finding` : "No finding"}
              </span>
            </div>
            <div className="verification-graph__columns">
              <div>
                <strong>Verification findings</strong>
                {selectedFindings.length ? (
                  <ul>
                    {selectedFindings.map((finding) => (
                      <li key={finding.id}>
                        <span className={`verification-severity verification-severity--${finding.severity.toLowerCase()}`}>
                          {finding.severity}
                        </span>
                        {finding.title}
                      </li>
                    ))}
                  </ul>
                ) : <p>No finding references this course in the selected run.</p>}
              </div>
              <div>
                <strong>Prerequisite chain</strong>
                <p>{upstream.length ? upstream.join(" → ") : "No upstream courses."}</p>
                <strong>Dependent chain</strong>
                <p>{downstream.length ? downstream.join(" → ") : "No downstream courses."}</p>
                <strong>Direct relationships</strong>
                {[...incoming, ...outgoing].length ? (
                  <ul>
                    {incoming.map((item) => (
                      <li key={item.id}>{item.prerequisite_course_code} → {item.target_course_code} <span>{item.status.replaceAll("_", " ").toLowerCase()}</span></li>
                    ))}
                    {outgoing.map((item) => (
                      <li key={item.id}>{item.prerequisite_course_code} → {item.target_course_code} <span>{item.status.replaceAll("_", " ").toLowerCase()}</span></li>
                    ))}
                  </ul>
                ) : <p>No direct prerequisite relationships.</p>}
              </div>
            </div>
          </>
        ) : <p>Select a course in the map.</p>}
      </div>

      <details className="verification-graph__table">
        <summary>Accessible course map table</summary>
        <table>
          <thead>
            <tr>
              <th>Course</th>
              <th>Semester</th>
              <th>Credits</th>
              <th>Findings</th>
              <th>Highest severity</th>
            </tr>
          </thead>
          <tbody>
            {activeCourses.map((course) => {
              const matched = courseFindings(course.id, findings);
              const severity = highestSeverity(matched);
              return (
                <tr key={course.id}>
                  <td>{course.course_code} · {course.course_name}</td>
                  <td>{course.semester_number}</td>
                  <td>{course.credits}</td>
                  <td>{matched.length}</td>
                  <td>{severity ? SEVERITY_LABEL[severity] : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    </div>
  );
}
