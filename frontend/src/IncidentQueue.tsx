import { useCallback, useEffect, useState } from 'react'

type Incident = {
  incident_id: string
  timestamp: string
  service_name: string
  severity: string
  anomaly_type: string
  description: string
  status: string
  trace_id?: string | null
  evidence?: {
    trace_id?: string | null
  } | null
}

type IncidentsResponse = {
  count: number
  incidents: Incident[]
}

type DetectionResponse = {
  incidents_created: number
}

type Props = {
  onTraceSelected: (traceId: string) => void
  onIncidentsUpdated: () => void
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleString()
}

export default function IncidentQueue({
  onTraceSelected,
  onIncidentsUpdated,
}: Props) {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [detecting, setDetecting] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadIncidents = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/incidents?limit=100', { signal })

      if (!response.ok) {
        throw new Error(`Could not load incidents: HTTP ${response.status}`)
      }

      const result = (await response.json()) as IncidentsResponse

      if (!signal?.aborted) {
        setIncidents(
          [...result.incidents].sort((a, b) =>
            b.timestamp.localeCompare(a.timestamp),
          ),
        )
      }
    } catch (caught) {
      if (!signal?.aborted) {
        setError(
          caught instanceof Error
            ? caught.message
            : 'Could not load incidents.',
        )
      }
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    void loadIncidents(controller.signal)

    return () => controller.abort()
  }, [loadIncidents])

  async function runDetection() {
    setDetecting(true)
    setMessage('')
    setError('')

    try {
      const response = await fetch('/api/detect/anomalies', {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`Anomaly detection failed: HTTP ${response.status}`)
      }

      const result = (await response.json()) as DetectionResponse

      setMessage(
        `${result.incidents_created} new incident${
          result.incidents_created === 1 ? '' : 's'
        } created.`,
      )

      await loadIncidents()
      onIncidentsUpdated()
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'Could not run anomaly detection.',
      )
    } finally {
      setDetecting(false)
    }
  }

  return (
    <section className="panel incident-panel" aria-labelledby="incidents-heading">
      <div className="panel-header incident-header">
        <div>
          <p className="eyebrow">DETECTION</p>
          <h2 id="incidents-heading">Incident queue</h2>
          <p className="incident-intro">
            Latest 100 stored incidents. Detection scans stored telemetry.
          </p>
        </div>

        <div className="incident-actions">
          <button
            type="button"
            disabled={loading || detecting}
            onClick={() => void loadIncidents()}
          >
            Refresh
          </button>
          <button
            className="detect-button"
            type="button"
            disabled={detecting}
            onClick={() => void runDetection()}
          >
            {detecting ? 'Detecting…' : 'Run detection'}
          </button>
        </div>
      </div>

      {message && <p className="incident-message" role="status">{message}</p>}
      {error && <p className="incident-error" role="alert">{error}</p>}

      {loading && incidents.length === 0 ? (
        <p className="empty-state">Loading incidents…</p>
      ) : incidents.length === 0 ? (
        <p className="empty-state">
          No incidents found. Generate a failure, then run detection.
        </p>
      ) : (
        <div className="incident-list">
          {incidents.map((incident) => {
            const traceId =
              incident.trace_id || incident.evidence?.trace_id

            return (
              <article className="incident-item" key={incident.incident_id}>
                <div className="incident-item-top">
                  <strong>{incident.service_name}</strong>
                  <span
                    className={`incident-severity ${
                      incident.severity === 'HIGH' ? 'high' : 'medium'
                    }`}
                  >
                    {incident.severity}
                  </span>
                  <time dateTime={incident.timestamp}>
                    {formatTime(incident.timestamp)}
                  </time>
                </div>

                <p>{incident.description}</p>

                <div className="incident-item-bottom">
                  <span>{incident.anomaly_type.replaceAll('_', ' ')}</span>
                  <span>Status: {incident.status}</span>

                  {traceId && (
                    <button
                      type="button"
                      onClick={() => onTraceSelected(traceId)}
                    >
                      Open trace →
                    </button>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}