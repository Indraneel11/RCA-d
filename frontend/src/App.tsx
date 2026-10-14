import { useCallback, useEffect, useMemo, useState } from 'react'

import DemoControls from './DemoControls'
import IncidentQueue from './IncidentQueue'
import RcaRanking from './RcaRanking'
import TraceEvidence from './TraceEvidence'
import './App.css'
import AskQuestion from './AskQuestion'

type Summary = {
  total_logs: number
  total_metrics: number
  total_traces: number
  total_incidents: number
  error_logs: number
  failed_trace_spans: number
  services_observed: string[]
}

type TraceSpan = {
  timestamp: string
  trace_id: string
  span_id: string
  parent_span_id: string | null
  service_name: string
  operation: string
  duration_ms: number
  status: string
}

type TracesResponse = {
  count: number
  traces: TraceSpan[]
}

type RootCause = {
  service_name: string
  score: number
  base_score?: number
  graph_bonus?: number
  confidence: string
  reasons: string[]
  evidence: {
    incident_count: number
    error_log_count: number
    failed_trace_count: number
    high_latency_metric_count: number
    correlated_trace_count: number
    upstream_failed_services?: string[]
  }
}

type RcaResponse = {
  message: string
  trace_id: string | null
  root_cause_service?: string
  confidence?: string
  explanation: string
  recommended_actions?: string[]
  rca_result: {
    events_analyzed: {
      incidents: number
      logs: number
      metrics: number
      traces: number
    }
    top_root_causes: RootCause[]
  }
}

type FailingTrace = {
  traceId: string
  timestamp: string
  failedServices: string[]
  spanCount: number
}

async function fetchJson<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(path, options)

  if (!response.ok) {
    throw new Error(`Request failed: HTTP ${response.status}`)
  }

  return response.json() as Promise<T>
}

function displayTime(timestamp: string): string {
  const date = new Date(timestamp)

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleString()
}

function orderSpans(spans: TraceSpan[]): TraceSpan[] {
  const byId = new Map(spans.map((span) => [span.span_id, span]))
  const children = new Map<string | null, TraceSpan[]>()

  for (const span of spans) {
    const parentId =
      span.parent_span_id && byId.has(span.parent_span_id)
        ? span.parent_span_id
        : null

    const siblings = children.get(parentId) ?? []
    siblings.push(span)
    children.set(parentId, siblings)
  }

  const ordered: TraceSpan[] = []
  const visited = new Set<string>()

  function visit(span: TraceSpan) {
    if (visited.has(span.span_id)) return

    visited.add(span.span_id)
    ordered.push(span)

    for (const child of children.get(span.span_id) ?? []) {
      visit(child)
    }
  }

  for (const root of children.get(null) ?? []) {
    visit(root)
  }

  // Include spans whose parent information is incomplete.
  for (const span of spans) {
    visit(span)
  }

  return ordered
}

function App() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [recentSpans, setRecentSpans] = useState<TraceSpan[]>([])
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [selectedSpans, setSelectedSpans] = useState<TraceSpan[]>([])
  const [rca, setRca] = useState<RcaResponse | null>(null)

  const [overviewLoading, setOverviewLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [overviewError, setOverviewError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const loadOverview = useCallback(async (signal?: AbortSignal) => {
    setOverviewLoading(true)
    setOverviewError(null)

    try {
      const [nextSummary, traceResponse] = await Promise.all([
        fetchJson<Summary>('/api/telemetry/summary', { signal }),
        fetchJson<TracesResponse>('/api/traces?limit=500', { signal }),
      ])

      if (signal?.aborted) return

      setSummary(nextSummary)
      setRecentSpans(traceResponse.traces)
      setLastUpdated(new Date())

      const failedIds = new Set(
        traceResponse.traces
          .filter((span) => span.status === 'error')
          .map((span) => span.trace_id),
      )

      const latestFailed = [...traceResponse.traces]
        .reverse()
        .find((span) => span.status === 'error')

      setSelectedTraceId((current) =>
        current && failedIds.has(current)
          ? current
          : latestFailed?.trace_id ?? null,
      )
    } catch (error) {
      if (signal?.aborted) return

      setOverviewError(
        error instanceof Error
          ? error.message
          : 'Could not load telemetry.',
      )
    } finally {
      if (!signal?.aborted) setOverviewLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    void loadOverview(controller.signal)

    return () => controller.abort()
  }, [loadOverview])

  const failingTraces = useMemo(() => {
    const grouped = new Map<string, FailingTrace>()

    for (const span of recentSpans) {
      const existing = grouped.get(span.trace_id)

      if (!existing) {
        grouped.set(span.trace_id, {
          traceId: span.trace_id,
          timestamp: span.timestamp,
          failedServices:
            span.status === 'error' ? [span.service_name] : [],
          spanCount: 1,
        })
        continue
      }

      existing.spanCount += 1

      if (span.timestamp > existing.timestamp) {
        existing.timestamp = span.timestamp
      }

      if (
        span.status === 'error' &&
        !existing.failedServices.includes(span.service_name)
      ) {
        existing.failedServices.push(span.service_name)
      }
    }

    return [...grouped.values()]
      .filter((trace) => trace.failedServices.length > 0)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
      .slice(0, 12)
  }, [recentSpans])

  useEffect(() => {
    if (!selectedTraceId) {
      setSelectedSpans([])
      setRca(null)
      setDetailError(null)
      return
    }

    const controller = new AbortController()
    const encodedId = encodeURIComponent(selectedTraceId)

    async function loadDetail() {
      setDetailLoading(true)
      setDetailError(null)
      setSelectedSpans([])
      setRca(null)

      try {
        const [traceResponse, explanation] = await Promise.all([
          fetchJson<TracesResponse>(
            `/api/traces?limit=500&trace_id=${encodedId}`,
            { signal: controller.signal },
          ),
          fetchJson<RcaResponse>(
            `/api/rca/explain?trace_id=${encodedId}`,
            {
              method: 'POST',
              signal: controller.signal,
            },
          ),
        ])

        if (controller.signal.aborted) return

        setSelectedSpans(orderSpans(traceResponse.traces))
        setRca(explanation)
      } catch (error) {
        if (controller.signal.aborted) return

        setDetailError(
          error instanceof Error
            ? error.message
            : 'Could not load this trace.',
        )
      } finally {
        if (!controller.signal.aborted) setDetailLoading(false)
      }
    }

    void loadDetail()

    return () => controller.abort()
  }, [selectedTraceId])

  const topCause = rca?.rca_result.top_root_causes[0]

  function openGeneratedTrace(traceId: string) {
    void loadOverview().then(() => {
      setSelectedTraceId(traceId)
    })
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">R</span>
          <div>
            <strong>RCA&apos;d</strong>
            <small>Observability workspace</small>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <div className="nav-item active">
          <span className="nav-dot" />
          Overview
        </div>

        <div className="sidebar-bottom">
          <span className="environment-dot" />
          Prototype environment
        </div>
      </aside>

      <main className="main-content">
        <header className="page-header">
          <div>
            <p className="eyebrow">OPERATIONS / OVERVIEW</p>
            <h1>Find what failed, then follow the evidence.</h1>
            <p className="page-description">
              Inspect recent telemetry and investigate a failing request.
            </p>
          </div>

          <button
            className="refresh-button"
            type="button"
            disabled={overviewLoading}
            onClick={() => void loadOverview()}
          >
            {overviewLoading ? 'Loading…' : '↻ Refresh data'}
          </button>
        </header>

        <DemoControls onTraceReady={openGeneratedTrace} />

        {overviewError && (
          <div className="error-banner" role="alert">
            <strong>Could not reach the backend.</strong> {overviewError}
            <span> Check that FastAPI is running on port 8000.</span>
          </div>
        )}

        <div className="section-heading">
          <div>
            <p className="eyebrow">SYSTEM SNAPSHOT</p>
            <h2>Telemetry overview</h2>
          </div>
          <span className="updated-label">
            {lastUpdated
              ? `Updated ${lastUpdated.toLocaleTimeString()}`
              : 'Waiting for data'}
          </span>
        </div>

        <section className="stats-grid" aria-label="Telemetry totals">
          <div className="stat-card">
            <span className="stat-label">Observed services</span>
            <strong>{summary?.services_observed.length ?? '—'}</strong>
            <small>Services sending telemetry</small>
          </div>

          <div className="stat-card">
            <span className="stat-label">Error logs</span>
            <strong>{summary?.error_logs ?? '—'}</strong>
            <small>Across stored logs</small>
          </div>

          <div className="stat-card">
            <span className="stat-label">Failed spans</span>
            <strong>{summary?.failed_trace_spans ?? '—'}</strong>
            <small>Across stored traces</small>
          </div>

          <div className="stat-card">
            <span className="stat-label">Recorded incidents</span>
            <strong>{summary?.total_incidents ?? '—'}</strong>
            <small>Created by detection runs</small>
          </div>
        </section>

        <section className="investigation-grid">
          <div className="panel trace-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">INVESTIGATE</p>
                <h2>Recent failing traces</h2>
              </div>
              <span className="panel-count">
                {failingTraces.length} shown
              </span>
            </div>

            {overviewLoading && !summary ? (
              <p className="empty-state">Loading traces…</p>
            ) : failingTraces.length === 0 ? (
              <p className="empty-state">
                No failing traces found in the latest 500 spans.
              </p>
            ) : (
              <div className="trace-list">
                {failingTraces.map((trace) => (
                  <button
                    className={`trace-row ${
                      selectedTraceId === trace.traceId ? 'selected' : ''
                    }`}
                    key={trace.traceId}
                    type="button"
                    aria-pressed={selectedTraceId === trace.traceId}
                    onClick={() => setSelectedTraceId(trace.traceId)}
                  >
                    <div className="trace-row-top">
                      <span className="failure-badge">FAILED</span>
                      <time dateTime={trace.timestamp}>
                        {displayTime(trace.timestamp)}
                      </time>
                    </div>

                    <strong title={trace.traceId}>
                      {trace.traceId}
                    </strong>

                    <span className="trace-row-bottom">
                      {trace.failedServices.join(' · ')}
                      <span>{trace.spanCount} spans</span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="panel detail-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">ROOT CAUSE ANALYSIS</p>
                <h2>Trace investigation</h2>
              </div>

              {selectedTraceId && (
                <span className="scope-badge">Single trace</span>
              )}
            </div>

            {!selectedTraceId ? (
              <p className="empty-state">
                Select a failing trace to see its evidence.
              </p>
            ) : (
              <>
                <div
                  className="selected-trace-id"
                  title={selectedTraceId}
                >
                  {selectedTraceId}
                </div>

                {detailLoading && (
                  <p className="empty-state">
                    Analyzing this trace…
                  </p>
                )}

                {detailError && (
                  <p className="detail-error" role="alert">
                    {detailError}
                  </p>
                )}

                {!detailLoading && !detailError && (
                  <>
                    <h3 className="subheading">Request path</h3>

                    <div className="span-list">
                      {selectedSpans.map((span) => (
                        <div className="span-item" key={span.span_id}>
                          <span
                            className={`span-indicator ${
                              span.status === 'error'
                                ? 'failed'
                                : 'success'
                            }`}
                          />
                          <div>
                            <strong>{span.service_name}</strong>
                            <small>{span.operation}</small>
                          </div>
                          <span className="duration">
                            {typeof span.duration_ms === 'number'
                              ? `${span.duration_ms.toFixed(0)} ms`
                              : '—'}
                          </span>
                        </div>
                      ))}
                    </div>

                    {topCause ? (
                      <div className="rca-card">
                        <p className="eyebrow">TOP RANKED SERVICE</p>

                        <div className="cause-heading">
                          <h3>{topCause.service_name}</h3>
                          <span className="confidence-badge">
                            {topCause.confidence}
                          </span>
                        </div>

                        <p className="score-note">
                          Rule-based score: {topCause.score}
                        </p>

                        <p className="explanation">
                          {rca?.explanation}
                        </p>

                        <div className="evidence-row">
                          <span>
                            {topCause.evidence.error_log_count} error logs
                          </span>
                          <span>
                            {topCause.evidence.failed_trace_count} failed
                            spans
                          </span>
                          <span>
                            {topCause.evidence.high_latency_metric_count}{' '}
                            high-latency metrics
                          </span>
                        </div>

                        <h4>Key evidence</h4>
                        <ul className="reason-list">
                          {topCause.reasons.slice(0, 4).map((reason) => (
                            <li key={reason}>{reason}</li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <p className="empty-state">
                        No root cause candidates were found for this
                        trace.
                      </p>
                    )}

                    <RcaRanking
                      candidates={rca?.rca_result.top_root_causes ?? []}
                      recommendedActions={
                        rca?.recommended_actions ?? []
                      }
                    />

                    <TraceEvidence traceId={selectedTraceId} />
                  </>
                )}
              </>
            )}
          </div>
        </section>

        <IncidentQueue
          onTraceSelected={setSelectedTraceId}
          onIncidentsUpdated={() => {
            void loadOverview()
          }}
        />
        <AskQuestion />

        <p className="footer-note">
          RCA rankings are diagnostic suggestions based on available
          evidence.
        </p>
      </main>
    </div>
  )
}

export default App