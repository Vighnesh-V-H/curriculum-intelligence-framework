"use client";

import { useMemo, useState } from "react";

import type { Course, CourseOutcome, Prerequisite } from "@/lib/api";

type Props = {
  courses: Course[];
  prerequisites: Prerequisite[];
  courseOutcomes: Record<string, CourseOutcome[]>;
};

type Edge = {
  prerequisite_course_id: string;
  target_course_id: string;
};

function reachableCourses(
  startId: string,
  edges: Edge[],
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

  return Array.from(seen).map((id) => courseById.get(id)?.course_code ?? id);
}

export function CurriculumGraph({ courses, prerequisites, courseOutcomes }: Props) {
  const active = useMemo(
    () => prerequisites.filter((item) => item.status !== "REJECTED"),
    [prerequisites],
  );
  const [selectedId, setSelectedId] = useState(courses[0]?.id ?? "");
  const selected = courses.find((course) => course.id === selectedId) ?? null;
  const courseById = useMemo(
    () => new Map(courses.map((course) => [course.id, course])),
    [courses],
  );

  const semesters = useMemo(() => {
    const numbers = Array.from(new Set(courses.map((course) => course.semester_number)))
      .sort((left, right) => left - right);
    return numbers.map((number) => ({
      number,
      courses: courses.filter((course) => course.semester_number === number),
    }));
  }, [courses]);

  const positions = useMemo(() => {
    const result = new Map<string, { x: number; y: number }>();
    semesters.forEach((semester, semesterIndex) => {
      semester.courses.forEach((course, courseIndex) => {
        result.set(course.id, {
          x: 110 + semesterIndex * 220,
          y: 60 + courseIndex * 70,
        });
      });
    });
    return result;
  }, [semesters]);

  const width = Math.max(640, semesters.length * 220 + 120);
  const height = Math.max(
    220,
    Math.max(...semesters.map((semester) => semester.courses.length), 1) * 70 + 90,
  );

  const incoming = selected
    ? active.filter((item) => item.target_course_id === selected.id)
    : [];
  const outgoing = selected
    ? active.filter((item) => item.prerequisite_course_id === selected.id)
    : [];
  const upstream = selected
    ? reachableCourses(selected.id, active, "upstream", courseById)
    : [];
  const downstream = selected
    ? reachableCourses(selected.id, active, "downstream", courseById)
    : [];

  return (
    <div className="academic-graph">
      <div className="academic-graph__canvas">
        <svg
          role="img"
          aria-label="Course prerequisite dependency graph grouped by semester"
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height={height}
        >
          <defs>
            <marker
              id="curriculum-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
            >
              <path d="M0,0 L8,4 L0,8 Z" fill="currentColor" />
            </marker>
          </defs>
          {semesters.map((semester, index) => (
            <text
              key={semester.number}
              x={110 + index * 220}
              y={24}
              textAnchor="middle"
              className="academic-graph__semester"
            >
              Semester {semester.number}
            </text>
          ))}
          {active.map((edge) => {
            const from = positions.get(edge.prerequisite_course_id);
            const to = positions.get(edge.target_course_id);
            if (!from || !to) return null;
            return (
              <path
                key={edge.id}
                d={`M ${from.x} ${from.y} C ${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x} ${to.y}`}
                className={`academic-graph__edge academic-graph__edge--${edge.status.toLowerCase()}`}
                markerEnd="url(#curriculum-arrow)"
              />
            );
          })}
          {semesters.flatMap((semester) =>
            semester.courses.map((course) => {
              const position = positions.get(course.id);
              if (!position) return null;
              const isSelected = course.id === selectedId;
              return (
                <g
                  key={course.id}
                  transform={`translate(${position.x}, ${position.y})`}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  aria-label={`${course.course_code} ${course.course_name}, semester ${course.semester_number}, ${course.credits} credits`}
                  className={
                    isSelected
                      ? "academic-graph__node is-selected"
                      : "academic-graph__node"
                  }
                  onClick={() => setSelectedId(course.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedId(course.id);
                    }
                  }}
                >
                  <circle r="22" />
                  <text y="4" textAnchor="middle">{course.course_code}</text>
                  <title>{course.course_code} · {course.course_name}</title>
                </g>
              );
            }),
          )}
        </svg>
        <p className="academic-graph__hint">
          Select a course to inspect its prerequisite chain. The table below lists
          the same relationships in an accessible format.
        </p>
      </div>

      <div className="academic-graph__detail">
        {selected ? (
          <>
            <h3>{selected.course_code} · {selected.course_name}</h3>
            <p>
              {selected.course_type_name} · {selected.credits} credits · Semester{" "}
              {selected.semester_number}
            </p>
            <p>{selected.description ?? "No course description."}</p>
            {selected.syllabus ? <pre>{selected.syllabus}</pre> : null}
            <div>
              <strong>Course outcomes</strong>
              {(courseOutcomes[selected.id] ?? []).length ? (
                <ul>
                  {(courseOutcomes[selected.id] ?? []).map((outcome) => (
                    <li key={outcome.id}>
                      <b>{outcome.co_code}</b> {outcome.description}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No course outcomes.</p>
              )}
            </div>
            <div>
              <strong>Requires</strong>
              {incoming.length ? (
                <ul>
                  {incoming.map((item) => (
                    <li key={item.id}>
                      {item.prerequisite_course_code}{" "}
                      <span>{item.status.replaceAll("_", " ").toLowerCase()}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No prerequisites.</p>
              )}
            </div>
            <div>
              <strong>Required before</strong>
              {outgoing.length ? (
                <ul>
                  {outgoing.map((item) => (
                    <li key={item.id}>
                      {item.target_course_code}{" "}
                      <span>{item.status.replaceAll("_", " ").toLowerCase()}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No dependent courses.</p>
              )}
            </div>
            <div>
              <strong>Full prerequisite chain</strong>
              <p>{upstream.length ? upstream.join(" → ") : "No upstream courses."}</p>
            </div>
            <div>
              <strong>Full dependent chain</strong>
              <p>{downstream.length ? downstream.join(" → ") : "No downstream courses."}</p>
            </div>
          </>
        ) : (
          <p className="academic-empty">Select a course in the graph.</p>
        )}
      </div>

      <div className="academic-graph__table">
        <h3>Accessible dependency table</h3>
        <table>
          <thead>
            <tr>
              <th>Prerequisite</th>
              <th>Target course</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {active.length ? (
              active.map((item) => (
                <tr key={item.id}>
                  <td>{item.prerequisite_course_code}</td>
                  <td>{item.target_course_code}</td>
                  <td>{item.status.replaceAll("_", " ")}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3}>No prerequisite relationships in this version.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
