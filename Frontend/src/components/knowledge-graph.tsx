"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  api,
  KnowledgeGraph,
  KnowledgeGraphNode,
  KnowledgeGraphRelationship,
} from "@/lib/api";

const NODE_ORDER = [
  "CurriculumVersion",
  "Semester",
  "Course",
  "CourseOutcome",
  "ProgramOutcome",
  "PEO",
] as const;

const NODE_TITLES: Record<string, string> = {
  CurriculumVersion: "Version",
  Semester: "Semester",
  Course: "Course",
  CourseOutcome: "Course outcome",
  ProgramOutcome: "Program outcome",
  PEO: "PEO",
};

const RELATIONSHIP_TITLES: Record<string, string> = {
  HAS_VERSION: "has version",
  FOR_PROGRAM: "for program",
  HAS_SEMESTER: "has semester",
  HAS_COURSE: "has course",
  SCHEDULED_IN: "scheduled in",
  HAS_OUTCOME: "has outcome",
  PREREQUISITE_OF: "is prerequisite of",
  CONTRIBUTES_TO: "contributes to",
  USES_PO: "uses program outcome",
  USES_PEO: "uses PEO",
};

const NODE_WIDTH = 168;
const NODE_HEIGHT = 44;
const COLUMN_WIDTH = 214;
const ROW_HEIGHT = 66;
const MAX_ROWS_PER_COLUMN = 12;
const MARGIN_X = 28;
const MARGIN_Y = 18;
const HEADER_HEIGHT = 34;

type Props = {
  curriculumId: string;
  versionId: string;
  canWrite: boolean;
};

type PositionedNode = {
  node: KnowledgeGraphNode;
  id: string;
  kind: string;
  x: number;
  y: number;
  primary: string;
  secondary: string;
  status: string;
};

type GraphError = {
  message: string;
  code: string;
};

type LayoutColumn = {
  kind: string;
  part: number;
  total: number;
  nodes: KnowledgeGraphNode[];
};

function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function nodeId(node: KnowledgeGraphNode): string {
  return textValue(node.properties.id);
}

function kindOf(node: KnowledgeGraphNode): string {
  for (const kind of NODE_ORDER) {
    if (node.labels.includes(kind)) return kind;
  }
  return node.labels[0] ?? "Node";
}

function kindTitle(kind: string): string {
  return NODE_TITLES[kind] ?? kind;
}

function nodePrimary(node: KnowledgeGraphNode, kind: string): string {
  const properties = node.properties;
  switch (kind) {
    case "CurriculumVersion":
      return `Version ${textValue(properties.version_label) || "—"}`;
    case "Semester":
      return `Semester ${textValue(properties.semester_number) || "—"}`;
    case "Course":
      return textValue(properties.course_code) || textValue(properties.id).slice(0, 8);
    case "CourseOutcome":
      return textValue(properties.co_code) || textValue(properties.id).slice(0, 8);
    case "ProgramOutcome":
      return textValue(properties.po_code) || textValue(properties.id).slice(0, 8);
    case "PEO":
      return textValue(properties.peo_code) || textValue(properties.id).slice(0, 8);
    default:
      return textValue(properties.id).slice(0, 10) || kind;
  }
}

function nodeSecondary(node: KnowledgeGraphNode, kind: string): string {
  const properties = node.properties;
  switch (kind) {
    case "CurriculumVersion":
      return textValue(properties.status).replaceAll("_", " ").toLowerCase();
    case "Semester":
      return textValue(properties.name) || "Unnamed semester";
    case "Course":
      return textValue(properties.course_name);
    case "CourseOutcome":
    case "ProgramOutcome":
    case "PEO":
      return textValue(properties.description);
    default:
      return "";
  }
}

function nodeStatus(node: KnowledgeGraphNode): string {
  return textValue(node.properties.status).toUpperCase();
}

function clip(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1)}…`;
}

function labelCase(value: string): string {
  return value.replaceAll("_", " ").toLowerCase();
}

function relationshipTitle(type: string): string {
  return RELATIONSHIP_TITLES[type] ?? labelCase(type);
}

function relationshipKey(relationship: KnowledgeGraphRelationship): string {
  return `${relationship.type}:${relationship.source_id}:${relationship.target_id}:${textValue(
    relationship.properties.id,
  )}`;
}

function sortValue(node: KnowledgeGraphNode, kind: string): string | number {
  const properties = node.properties;
  switch (kind) {
    case "Semester":
      return Number(properties.semester_number) || 0;
    case "Course":
      return textValue(properties.course_code);
    case "CourseOutcome":
      return textValue(properties.co_code);
    case "ProgramOutcome":
      return textValue(properties.po_code);
    case "PEO":
      return textValue(properties.peo_code);
    case "CurriculumVersion":
      return textValue(properties.version_label);
    default:
      return textValue(properties.id);
  }
}

function buildLayout(nodes: KnowledgeGraphNode[]) {
  const groups = new Map<string, KnowledgeGraphNode[]>();
  for (const node of nodes) {
    const kind = kindOf(node);
    const group = groups.get(kind) ?? [];
    group.push(node);
    groups.set(kind, group);
  }

  const orderedKinds = [
    ...NODE_ORDER.filter((kind) => groups.has(kind)),
    ...Array.from(groups.keys())
      .filter((kind) => !(NODE_ORDER as readonly string[]).includes(kind))
      .sort(),
  ];

  const columns: LayoutColumn[] = [];
  for (const kind of orderedKinds) {
    const kindNodes = [...(groups.get(kind) ?? [])].sort((left, right) => {
      const leftValue = sortValue(left, kind);
      const rightValue = sortValue(right, kind);
      if (typeof leftValue === "number" && typeof rightValue === "number") {
        return leftValue - rightValue;
      }
      return String(leftValue).localeCompare(String(rightValue), undefined, {
        numeric: true,
        sensitivity: "base",
      });
    });
    const total = Math.max(1, Math.ceil(kindNodes.length / MAX_ROWS_PER_COLUMN));
    for (let part = 0; part < total; part += 1) {
      columns.push({
        kind,
        part: part + 1,
        total,
        nodes: kindNodes.slice(
          part * MAX_ROWS_PER_COLUMN,
          (part + 1) * MAX_ROWS_PER_COLUMN,
        ),
      });
    }
  }

  const positions = new Map<string, PositionedNode>();
  for (const [columnIndex, column] of columns.entries()) {
    for (const [rowIndex, node] of column.nodes.entries()) {
      const id = nodeId(node);
      if (!id) continue;
      positions.set(id, {
        node,
        id,
        kind: column.kind,
        x: MARGIN_X + columnIndex * COLUMN_WIDTH + COLUMN_WIDTH / 2,
        y:
          MARGIN_Y +
          HEADER_HEIGHT +
          rowIndex * ROW_HEIGHT +
          ROW_HEIGHT / 2,
        primary: nodePrimary(node, column.kind),
        secondary: nodeSecondary(node, column.kind),
        status: nodeStatus(node),
      });
    }
  }

  const maxRows = Math.max(...columns.map((column) => column.nodes.length), 1);
  return {
    columns,
    positions,
    width: Math.max(640, MARGIN_X * 2 + columns.length * COLUMN_WIDTH),
    height: Math.max(
      220,
      MARGIN_Y * 2 + HEADER_HEIGHT + maxRows * ROW_HEIGHT,
    ),
  };
}

function edgePath(from: PositionedNode, to: PositionedNode): string {
  if (from.id === to.id) return "";
  if (Math.abs(from.x - to.x) < 1) {
    const startX = from.x + NODE_WIDTH / 2;
    const startY = from.y;
    const endY = to.y;
    const bend = 70;
    return `M ${startX} ${startY} C ${startX + bend} ${startY}, ${
      startX + bend
    } ${endY}, ${startX} ${endY}`;
  }

  const direction = to.x > from.x ? 1 : -1;
  const startX = from.x + (direction * NODE_WIDTH) / 2;
  const endX = to.x - (direction * NODE_WIDTH) / 2;
  const control = Math.max(36, Math.abs(endX - startX) * 0.4) * direction;
  return `M ${startX} ${from.y} C ${startX + control} ${from.y}, ${
    endX - control
  } ${to.y}, ${endX} ${to.y}`;
}

function initialVisibility(): Record<string, boolean> {
  return Object.fromEntries(NODE_ORDER.map((kind) => [kind, true]));
}

export function KnowledgeGraphPanel({ curriculumId, versionId, canWrite }: Props) {
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<GraphError | null>(null);
  const [notice, setNotice] = useState("");
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedId, setSelectedId] = useState("");
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(1);
  const [visibleKinds, setVisibleKinds] =
    useState<Record<string, boolean>>(initialVisibility);

  useEffect(() => {
    let cancelled = false;

    api
      .getKnowledgeGraph(curriculumId, versionId)
      .then((data) => {
        if (!cancelled) setGraph(data);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setGraph(null);
        setError(
          caught instanceof ApiError
            ? { message: caught.message, code: caught.code }
            : {
                message: "The Neo4j graph projection could not be loaded.",
                code: "request_failed",
              },
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [curriculumId, versionId, reloadToken]);

  const nodes = useMemo(() => graph?.nodes ?? [], [graph]);
  const relationships = useMemo(() => graph?.relationships ?? [], [graph]);

  const kindCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const node of nodes) {
      const kind = kindOf(node);
      counts[kind] = (counts[kind] ?? 0) + 1;
    }
    return counts;
  }, [nodes]);

  const presentKinds = useMemo(() => {
    const found = new Set(nodes.map(kindOf));
    return [
      ...NODE_ORDER.filter((kind) => found.has(kind)),
      ...Array.from(found)
        .filter((kind) => !(NODE_ORDER as readonly string[]).includes(kind))
        .sort(),
    ];
  }, [nodes]);

  const visibleNodes = useMemo(
    () => nodes.filter((node) => visibleKinds[kindOf(node)] !== false),
    [nodes, visibleKinds],
  );

  const layout = useMemo(() => buildLayout(visibleNodes), [visibleNodes]);

  const visibleRelationships = useMemo(
    () =>
      relationships.filter(
        (relationship) =>
          layout.positions.has(relationship.source_id) &&
          layout.positions.has(relationship.target_id),
      ),
    [relationships, layout.positions],
  );

  const matchedIds = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return null;
    const matches = new Set<string>();
    for (const node of visibleNodes) {
      const searchable = [
        ...node.labels,
        ...Object.values(node.properties).map(textValue),
      ]
        .join(" ")
        .toLowerCase();
      if (searchable.includes(normalized)) matches.add(nodeId(node));
    }
    return matches;
  }, [query, visibleNodes]);

  const neighbourIds = useMemo(() => {
    if (!selectedId) return null;
    const neighbours = new Set<string>([selectedId]);
    for (const relationship of relationships) {
      if (relationship.source_id === selectedId) {
        neighbours.add(relationship.target_id);
      }
      if (relationship.target_id === selectedId) {
        neighbours.add(relationship.source_id);
      }
    }
    return neighbours;
  }, [relationships, selectedId]);

  const selected = layout.positions.get(selectedId) ?? null;
  const selectedRelationships = selected
    ? relationships.filter(
        (relationship) =>
          relationship.source_id === selected.id ||
          relationship.target_id === selected.id,
      )
    : [];

  function toggleKind(kind: string) {
    if (visibleKinds[kind] !== false && selected?.kind === kind) {
      setSelectedId("");
    }
    setVisibleKinds((current) => ({
      ...current,
      [kind]: current[kind] === false,
    }));
  }

  const resetView = useCallback(() => {
    setVisibleKinds(initialVisibility());
    setSelectedId("");
    setQuery("");
    setZoom(1);
  }, []);

  function refreshGraph() {
    setLoading(true);
    setError(null);
    setReloadToken((token) => token + 1);
  }

  async function rebuildProjection() {
    setRebuilding(true);
    setError(null);
    setNotice("");
    try {
      const result = await api.rebuildKnowledgeGraph(curriculumId, versionId);
      setNotice(
        `Projection rebuilt: ${result.node_count} nodes and ${result.relationship_count} relationships.`,
      );
      refreshGraph();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? { message: caught.message, code: caught.code }
          : {
              message: "The graph projection could not be rebuilt.",
              code: "request_failed",
            },
      );
    } finally {
      setRebuilding(false);
    }
  }

  function isDimmed(id: string): boolean {
    if (neighbourIds && !neighbourIds.has(id)) return true;
    if (matchedIds && !matchedIds.has(id)) return true;
    return false;
  }

  function edgeIsDimmed(relationship: KnowledgeGraphRelationship): boolean {
    if (
      selectedId &&
      relationship.source_id !== selectedId &&
      relationship.target_id !== selectedId
    ) {
      return true;
    }
    if (
      matchedIds &&
      !matchedIds.has(relationship.source_id) &&
      !matchedIds.has(relationship.target_id)
    ) {
      return true;
    }
    return false;
  }

  const projectionLabel = graph
    ? graph.is_current
      ? "Current"
      : graph.projection_status === "COMPLETED"
        ? "Stale"
        : labelCase(graph.projection_status || "not built")
    : "Not loaded";

  return (
    <div className="knowledge-graph">
      <div className="knowledge-graph__bar">
        <div className="knowledge-graph__status">
          {graph ? (
            <>
              <span
                className={
                  graph.is_current
                    ? "knowledge-graph__badge is-current"
                    : "knowledge-graph__badge is-stale"
                }
              >
                {projectionLabel}
              </span>
              <span>{nodes.length} nodes</span>
              <span>{relationships.length} relationships</span>
              {!graph.is_current && graph.projection_status ? (
                <span>Projection {labelCase(graph.projection_status)}</span>
              ) : null}
            </>
          ) : (
            <span>Version-scoped Neo4j snapshot</span>
          )}
        </div>
        <div className="knowledge-graph__actions">
          {canWrite ? (
            <button
              type="button"
              onClick={() => void rebuildProjection()}
              disabled={rebuilding || loading}
            >
              {rebuilding ? "Rebuilding…" : "Rebuild projection"}
            </button>
          ) : null}
          <button
            type="button"
            className="knowledge-graph__secondary"
            onClick={refreshGraph}
            disabled={loading || rebuilding}
          >
            {loading && graph ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {notice ? (
        <p className="academic-alert" role="status">
          {notice}
        </p>
      ) : null}

      {error ? (
        error.code === "graph_unavailable" ? (
          <div className="knowledge-graph__state knowledge-graph__state--setup">
            <strong>Neo4j is not connected</strong>
            <p>
              The API returned <code>graph_unavailable</code>, so there is no
              projection to display. The relational curriculum remains fully
              available.
            </p>
            <ol>
              <li>
                Start Neo4j and add <code>NEO4J_URI</code>,{" "}
                <code>NEO4J_USERNAME</code>, <code>NEO4J_PASSWORD</code>, and
                optionally <code>NEO4J_DATABASE</code> to{" "}
                <code>backend/.env</code>.
              </li>
              <li>Restart the API so it opens the driver.</li>
              <li>
                {canWrite
                  ? "Use Rebuild projection above to project this curriculum version."
                  : "Ask a curriculum writer to rebuild this version's projection."}
              </li>
            </ol>
            <pre>{`NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j`}</pre>
            <p>
              Keep the projection fresh with{" "}
              <code>uv run python -m app.workers.graph_projection</code>.
            </p>
          </div>
        ) : (
          <div className="knowledge-graph__state knowledge-graph__state--error">
            <strong>Graph projection unavailable</strong>
            <p>{error.message}</p>
            <button type="button" onClick={refreshGraph}>
              Try again
            </button>
          </div>
        )
      ) : null}

      {loading && !graph ? (
        <div className="knowledge-graph__skeleton" aria-label="Loading graph">
          <div />
          <div />
          <div />
        </div>
      ) : null}

      {!loading && !error && graph && nodes.length === 0 ? (
        <div className="knowledge-graph__state">
          <strong>No projection has been built for this version</strong>
          <p>
            {canWrite
              ? "Rebuild the projection to copy this curriculum version into Neo4j."
              : "A curriculum writer must rebuild this version's projection before it can be explored here."}
          </p>
          {canWrite ? (
            <button
              type="button"
              onClick={() => void rebuildProjection()}
              disabled={rebuilding}
            >
              {rebuilding ? "Rebuilding…" : "Rebuild projection"}
            </button>
          ) : null}
        </div>
      ) : null}

      {!loading && !error && graph && nodes.length > 0 ? (
        <>
          <div className="knowledge-graph__toolbar">
            <label className="knowledge-graph__search">
              Find a node
              <input
                type="search"
                value={query}
                placeholder="Course code, CO, PO, status…"
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div
              className="knowledge-graph__filters"
              aria-label="Show node types"
            >
              {presentKinds.map((kind) => (
                <label className="knowledge-graph__filter" key={kind}>
                  <input
                    type="checkbox"
                    checked={visibleKinds[kind] !== false}
                    onChange={() => toggleKind(kind)}
                  />
                  {kindTitle(kind)}
                  <small>{kindCounts[kind] ?? 0}</small>
                </label>
              ))}
            </div>
            <label className="knowledge-graph__zoom">
              Zoom
              <select
                value={zoom}
                onChange={(event) => setZoom(Number(event.target.value))}
              >
                <option value={0.75}>75%</option>
                <option value={1}>100%</option>
                <option value={1.25}>125%</option>
                <option value={1.5}>150%</option>
              </select>
            </label>
            <button
              type="button"
              className="knowledge-graph__secondary"
              onClick={resetView}
            >
              Reset view
            </button>
          </div>

          {visibleNodes.length === 0 ? (
            <div className="knowledge-graph__state">
              <strong>All node types are hidden</strong>
              <p>
                Use the type filters above to make at least one kind of node
                visible again.
              </p>
              <button type="button" onClick={resetView}>
                Show all node types
              </button>
            </div>
          ) : (
            <>
          <div className="knowledge-graph__body">
            <div
              className="knowledge-graph__canvas"
              tabIndex={0}
              aria-label="Scrollable knowledge graph canvas"
            >
              <svg
                role="img"
                aria-label={`Neo4j knowledge graph with ${visibleNodes.length} visible nodes and ${visibleRelationships.length} visible relationships`}
                viewBox={`0 0 ${layout.width} ${layout.height}`}
                width={layout.width * zoom}
                height={layout.height * zoom}
              >
                <defs>
                  <marker
                    id="knowledge-graph-arrow"
                    markerWidth="7"
                    markerHeight="7"
                    refX="7"
                    refY="3.5"
                    orient="auto"
                  >
                    <path
                      d="M0,0 L7,3.5 L0,7 Z"
                      fill="var(--muted-foreground)"
                    />
                  </marker>
                </defs>

                {layout.columns.map((column, columnIndex) => (
                  <text
                    key={`${column.kind}-${column.part}`}
                    x={MARGIN_X + (columnIndex + 0.5) * COLUMN_WIDTH}
                    y={MARGIN_Y + 12}
                    textAnchor="middle"
                    className="knowledge-graph__column"
                  >
                    {kindTitle(column.kind)}
                    {column.total > 1 ? ` ${column.part}/${column.total}` : ""}
                  </text>
                ))}

                {visibleRelationships.map((relationship) => {
                  const from = layout.positions.get(relationship.source_id);
                  const to = layout.positions.get(relationship.target_id);
                  if (!from || !to) return null;
                  const status = textValue(
                    relationship.properties.status,
                  ).toLowerCase();
                  const typeClass = relationship.type
                    .toLowerCase()
                    .replaceAll("_", "-");
                  const classes = [
                    "knowledge-graph__edge",
                    `knowledge-graph__edge--${typeClass}`,
                    status ? `is-${status.toLowerCase()}` : "",
                    edgeIsDimmed(relationship) ? "is-dimmed" : "",
                  ]
                    .filter(Boolean)
                    .join(" ");
                  return (
                    <path
                      key={relationshipKey(relationship)}
                      d={edgePath(from, to)}
                      className={classes}
                      markerEnd="url(#knowledge-graph-arrow)"
                    >
                      <title>
                        {`${from.primary} ${relationshipTitle(
                          relationship.type,
                        )} ${to.primary}${
                          status ? ` (${labelCase(status)})` : ""
                        }`}
                      </title>
                    </path>
                  );
                })}

                {Array.from(layout.positions.values()).map((position) => {
                  const status = position.status.toLowerCase();
                  const classes = [
                    "knowledge-graph__node",
                    `knowledge-graph__node--${position.kind.toLowerCase()}`,
                    status ? `is-${status}` : "",
                    position.id === selectedId ? "is-selected" : "",
                    matchedIds?.has(position.id) ? "is-matched" : "",
                    isDimmed(position.id) ? "is-dimmed" : "",
                  ]
                    .filter(Boolean)
                    .join(" ");
                  return (
                    <g
                      key={position.id}
                      transform={`translate(${position.x}, ${position.y})`}
                      tabIndex={0}
                      role="button"
                      aria-pressed={position.id === selectedId}
                      aria-label={`${kindTitle(position.kind)} ${position.primary}${
                        position.secondary ? `, ${position.secondary}` : ""
                      }`}
                      className={classes}
                      onClick={() => setSelectedId(position.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId(position.id);
                        }
                      }}
                    >
                      <rect
                        x={-NODE_WIDTH / 2}
                        y={-NODE_HEIGHT / 2}
                        width={NODE_WIDTH}
                        height={NODE_HEIGHT}
                        rx={6}
                      />
                      <text
                        y={-3}
                        textAnchor="middle"
                        className="knowledge-graph__node-primary"
                      >
                        {clip(position.primary, 26)}
                      </text>
                      <text
                        y={11}
                        textAnchor="middle"
                        className="knowledge-graph__node-secondary"
                      >
                        {clip(position.secondary, 31)}
                      </text>
                      <title>
                        {`${kindTitle(position.kind)} · ${position.primary}${
                          position.secondary ? ` · ${position.secondary}` : ""
                        }`}
                      </title>
                    </g>
                  );
                })}
              </svg>
            </div>

            <aside className="knowledge-graph__detail" aria-live="polite">
              {selected ? (
                <>
                  <header>
                    <span className="knowledge-graph__kind">
                      {kindTitle(selected.kind)}
                    </span>
                    <button
                      type="button"
                      className="knowledge-graph__link"
                      onClick={() => setSelectedId("")}
                    >
                      Clear
                    </button>
                  </header>
                  <h3>{selected.primary}</h3>
                  <p>{selected.secondary || "No additional description."}</p>
                  <dl className="knowledge-graph__facts">
                    <div>
                      <dt>Status</dt>
                      <dd>{selected.status || "—"}</dd>
                    </div>
                    <div>
                      <dt>Connections</dt>
                      <dd>{selectedRelationships.length}</dd>
                    </div>
                    <div>
                      <dt>Graph id</dt>
                      <dd title={selected.id}>{selected.id.slice(0, 13)}…</dd>
                    </div>
                  </dl>
                  <div className="knowledge-graph__relations">
                    <strong>Relationships</strong>
                    {selectedRelationships.length ? (
                      <ul>
                        {selectedRelationships.map((relationship) => {
                          const outgoing =
                            relationship.source_id === selected.id;
                          const otherId = outgoing
                            ? relationship.target_id
                            : relationship.source_id;
                          const other = layout.positions.get(otherId);
                          const status = textValue(
                            relationship.properties.status,
                          );
                          return (
                            <li key={relationshipKey(relationship)}>
                              <span className="knowledge-graph__relation-type">
                                {outgoing ? "→" : "←"}{" "}
                                {relationshipTitle(relationship.type)}
                              </span>
                              <span>{other?.primary ?? otherId.slice(0, 8)}</span>
                              {status ? (
                                <small>{labelCase(status)}</small>
                              ) : null}
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <p>No relationships for this node.</p>
                    )}
                  </div>
                </>
              ) : (
                <div className="knowledge-graph__detail-empty">
                  <strong>Inspect a node</strong>
                  <p>
                    Select a course, outcome, semester, or version in the graph
                    to see its relationships. Filter node types or search to
                    reduce a large curriculum.
                  </p>
                </div>
              )}
            </aside>
          </div>

          <p className="knowledge-graph__hint">
            Node positions follow entity type. Select a node to trace one hop;
            the tables below contain the same data in an accessible format.
          </p>

          <details className="knowledge-graph__data">
            <summary>
              Accessible graph data
              <span>
                {visibleNodes.length} nodes · {visibleRelationships.length}{" "}
                relationships
              </span>
            </summary>
            <div className="knowledge-graph__data-grid">
              <section>
                <h3>Nodes</h3>
                <div className="knowledge-graph__table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Code / label</th>
                        <th>Description</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleNodes.map((node) => {
                        const kind = kindOf(node);
                        return (
                          <tr key={nodeId(node)}>
                            <td>{kindTitle(kind)}</td>
                            <td>{nodePrimary(node, kind)}</td>
                            <td>{nodeSecondary(node, kind) || "—"}</td>
                            <td>{nodeStatus(node) || "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
              <section>
                <h3>Relationships</h3>
                <div className="knowledge-graph__table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Source</th>
                        <th>Relationship</th>
                        <th>Target</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRelationships.map((relationship) => {
                        const from = layout.positions.get(
                          relationship.source_id,
                        );
                        const to = layout.positions.get(relationship.target_id);
                        return (
                          <tr key={relationshipKey(relationship)}>
                            <td>{from?.primary ?? relationship.source_id}</td>
                            <td>{relationshipTitle(relationship.type)}</td>
                            <td>{to?.primary ?? relationship.target_id}</td>
                            <td>
                              {textValue(relationship.properties.status) ||
                                "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </details>
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
