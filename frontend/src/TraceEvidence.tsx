import { useEffect, useState } from 'react'

type LogEvent = {
  timestamp: string
  service_name: string
  level: string
  message: string
}

type MetricEvent = {
  timestamp: string
  service_name: string
  metric_name: string
  value: number
  unit: string
}

type LogsResponse = {
  logs: LogEvent[]
}

type MetricsResponse = {
  metrics: MetricEvent[]
}

type TraceEvidenceProps = {
  traceId: string
}

async function getJson<T>(
  url: string,
  signal: AbortSignal,
): Promise<T> {
  const response = await fetch(url, { signal })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  return response.json() as Promise<T>
}

export default function TraceEvidence({ traceId }: TraceEvidenceProps) {
  const [logs, setLogs] = useState<LogEvent[]>([])
  const [metrics, setMetrics] = useState<MetricEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const encodedId = encodeURIComponent(traceId)

    async function loadEvidence() {
      setLoading(true)
      setError(null)
      setLogs([])
      setMetrics([])

      try {
        const [logResponse, metricResponse] = await Promise.all([
          getJson<LogsResponse>(
            `/api/logs?limit=500&trace_id=${encodedId}`,
            controller.signal,
          ),
          getJson<MetricsResponse>(
            `/api/metrics?limit=500&trace_id=${encodedId}`,
            controller.signal,
          ),
        ])

        if (controller.signal.aborted) return

        setLogs(logResponse.logs)
        setMetrics(metricResponse.metrics)
      } catch (caught) {
        if (controller.signal.aborted) return

        setError(
          caught instanceof Error
            ? caught.message
            : 'Could not load trace evidence.',
        )
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    void loadEvidence()

    return () => controller.abort()
  }, [traceId])

  return (
    <section className="telemetry-panel">
      <div className="telemetry-heading">
        <div>
          <p className="eyebrow">SOURCE EVENTS</p>
          <h3>Logs and metrics</h3>
        </div>
        {!loading && !error && (
          <span className="panel-count">
            {logs.length} logs · {metrics.length} metrics
          </span>
        )}
      </div>

      {loading && <p className="empty-state">Loading source events…</p>}

      {error && (
        <p className="detail-error" role="alert">
          Could not load source events: {error}
        </p>
      )}

      {!loading && !error && (
        <div className="telemetry-columns">
          <div>
            <h4>Logs</h4>
            {logs.length === 0 ? (
              <p className="evidence-empty">No logs for this trace.</p>
            ) : (
              <div className="event-list">
                {logs.map((log, index) => (
                  <div className="event-card" key={`${log.timestamp}-${index}`}>
                    <div className="event-top">
                      <strong>{log.service_name}</strong>
                      <span
                        className={
                          log.level === 'ERROR'
                            ? 'event-level error'
                            : 'event-level'
                        }
                      >
                        {log.level}
                      </span>
                    </div>
                    <p>{log.message}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h4>Metrics</h4>
            {metrics.length === 0 ? (
              <p className="evidence-empty">
                No request-specific metrics for this trace.
              </p>
            ) : (
              <div className="event-list">
                {metrics.map((metric, index) => (
                  <div
                    className="event-card metric-card"
                    key={`${metric.timestamp}-${index}`}
                  >
                    <div>
                      <strong>{metric.service_name}</strong>
                      <small>{metric.metric_name}</small>
                    </div>
                    <span className="metric-value">
                      {metric.value.toFixed(1)} {metric.unit}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}