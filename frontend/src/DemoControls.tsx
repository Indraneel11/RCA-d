import { useState } from 'react'

type FailureType = 'payment_timeout' | 'payment_error' | 'order_error'

type SimulationResponse = {
  results: Array<{
    trace_id: string
    failure_type: string
    status: string
  }>
}

type CountResponse<T> = {
  count: number
  traces?: T[]
  logs?: T[]
  metrics?: T[]
}

type Props = {
  onTraceReady: (traceId: string) => void
}

const scenarios: { value: FailureType; label: string }[] = [
  { value: 'payment_timeout', label: 'Payment timeout' },
  { value: 'payment_error', label: 'Payment gateway error' },
  { value: 'order_error', label: 'Order processing error' },
]

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function readJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)

  if (!response.ok) {
    throw new Error(`Request failed: HTTP ${response.status}`)
  }

  return response.json() as Promise<T>
}

async function waitForTelemetry(
  traceId: string,
  expectedEvents: number,
): Promise<boolean> {
  const encodedId = encodeURIComponent(traceId)

  for (let attempt = 0; attempt < 15; attempt += 1) {
    const [traces, logs, metrics] = await Promise.all([
      readJson<CountResponse<unknown>>(
        `/api/traces?limit=500&trace_id=${encodedId}`,
      ),
      readJson<CountResponse<unknown>>(
        `/api/logs?limit=500&trace_id=${encodedId}`,
      ),
      readJson<CountResponse<unknown>>(
        `/api/metrics?limit=500&trace_id=${encodedId}`,
      ),
    ])

    if (
      traces.count >= expectedEvents &&
      logs.count >= expectedEvents &&
      metrics.count >= expectedEvents
    ) {
      return true
    }

    await wait(600)
  }

  return false
}

export default function DemoControls({ onTraceReady }: Props) {
  const [failureType, setFailureType] =
    useState<FailureType>('payment_timeout')
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function runDemo() {
    setRunning(true)
    setMessage('Generating the request…')
    setError('')

    try {
      const result = await readJson<SimulationResponse>(
        `/api/simulate?count=1&failure_type=${failureType}`,
        { method: 'POST' },
      )

      const generated = result.results[0]

      if (!generated?.trace_id) {
        throw new Error('The simulator did not return a trace ID.')
      }

      setMessage('Waiting for the Kafka consumer to store telemetry…')

      const expectedEvents = failureType === 'order_error' ? 2 : 3
      const ready = await waitForTelemetry(
        generated.trace_id,
        expectedEvents,
      )

      if (!ready) {
        throw new Error(
          `The request was generated (${generated.trace_id}), but its telemetry has not arrived. Check that the Kafka consumer is running, then refresh the dashboard.`,
        )
      }

      onTraceReady(generated.trace_id)
      setMessage(`Opened ${generated.trace_id}`)
    } catch (caught) {
      setMessage('')
      setError(
        caught instanceof Error ? caught.message : 'Could not run the demo.',
      )
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="demo-controls" aria-labelledby="demo-heading">
      <div>
        <p className="eyebrow">GUIDED DEMO</p>
        <h2 id="demo-heading">Generate a failure</h2>
        <p>
          Create one request with a known failure, then inspect its trace,
          telemetry, and root cause.
        </p>
      </div>

      <div className="demo-controls-form">
        <label htmlFor="demo-scenario">Scenario</label>
        <select
          id="demo-scenario"
          value={failureType}
          disabled={running}
          onChange={(event) =>
            setFailureType(event.target.value as FailureType)
          }
        >
          {scenarios.map((scenario) => (
            <option key={scenario.value} value={scenario.value}>
              {scenario.label}
            </option>
          ))}
        </select>

        <button type="button" disabled={running} onClick={() => void runDemo()}>
          {running ? 'Running…' : 'Run demo'}
        </button>
      </div>

      {message && <p className="demo-message" role="status">{message}</p>}
      {error && <p className="demo-error" role="alert">{error}</p>}
    </section>
  )
}