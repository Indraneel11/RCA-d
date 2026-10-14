type Candidate = {
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

type Props = {
  candidates: Candidate[]
  recommendedActions: string[]
}

export default function RcaRanking({
  candidates,
  recommendedActions,
}: Props) {
  if (candidates.length === 0) return null

  return (
    <section className="ranking-panel" aria-labelledby="ranking-heading">
      <h3 id="ranking-heading">Ranked root cause candidates</h3>
      <p className="ranking-intro">
        These are rule-based diagnostic rankings for the selected trace.
        HIGH, MEDIUM, and LOW are score bands, not probabilities.
      </p>

      <ol className="candidate-list">
        {candidates.map((candidate, index) => (
          <li className="candidate-item" key={candidate.service_name}>
            <div className="candidate-heading">
              <div>
                <span className="candidate-number">#{index + 1}</span>
                <strong>{candidate.service_name}</strong>
              </div>
              <span className="candidate-score">
                Score {candidate.score} · {candidate.confidence}
              </span>
            </div>

            {candidate.base_score !== undefined && (
              <p className="candidate-breakdown">
                Telemetry score {candidate.base_score} + call-chain bonus{' '}
                {candidate.graph_bonus ?? 0}
              </p>
            )}

            <div className="candidate-evidence">
              <span>{candidate.evidence.error_log_count} error logs</span>
              <span>
                {candidate.evidence.failed_trace_count} failed spans
              </span>
              <span>
                {candidate.evidence.high_latency_metric_count} latency
                signals
              </span>
              {candidate.evidence.correlated_trace_count > 0 && (
                <span>
                  {candidate.evidence.correlated_trace_count} correlated
                  traces
                </span>
              )}
            </div>

            {candidate.reasons.length > 0 && (
              <p className="candidate-reason">
                {candidate.reasons[0]}
              </p>
            )}
          </li>
        ))}
      </ol>

      {recommendedActions.length > 0 && (
        <div className="recommended-actions">
          <h4>Recommended next checks for {candidates[0].service_name}</h4>
          <ol>
            {recommendedActions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}