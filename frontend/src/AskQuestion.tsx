import { useState, type FormEvent } from 'react'

type QueryResponse = {
  message?: string
  model?: string
  answer?: string | null
  error?: string
}

export default function AskQuestion() {
  const [question, setQuestion] = useState('')
  const [minutes, setMinutes] = useState(10)
  const [answer, setAnswer] = useState('')
  const [model, setModel] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const trimmedQuestion = question.trim()
    if (!trimmedQuestion) return

    setLoading(true)
    setAnswer('')
    setModel('')
    setError('')

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          minutes,
        }),
      })

      if (!response.ok) {
        throw new Error(`Question request failed: HTTP ${response.status}`)
      }

      const result = (await response.json()) as QueryResponse

      if (result.error) {
        throw new Error(result.error)
      }

      if (result.message === 'GEMINI_API_KEY is not configured') {
        throw new Error(result.answer || result.message)
      }

      if (!result.answer?.trim()) {
        throw new Error(
          result.message || 'The query returned no answer.',
        )
      }

      setAnswer(result.answer)
      setModel(result.model ?? '')
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'Could not answer the question.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel question-panel" aria-labelledby="question-heading">
      <div className="panel-header">
        <div>
          <p className="eyebrow">ASK THE DATA</p>
          <h2 id="question-heading">Observability question</h2>
        </div>
        <span className="scope-badge">System-wide time window</span>
      </div>

      <p className="question-help">
        Ask about recent telemetry and incidents. The AI uses the chosen
        time window, independently of the selected trace.
      </p>

      <form className="question-form" onSubmit={(event) => void submitQuestion(event)}>
        <label htmlFor="observability-question">Question</label>
        <textarea
          id="observability-question"
          rows={3}
          value={question}
          maxLength={1000}
          disabled={loading}
          placeholder="What is the likely cause of recent payment failures?"
          onChange={(event) => setQuestion(event.target.value)}
        />

        <div className="question-form-bottom">
          <label htmlFor="question-window">Time window</label>
          <select
            id="question-window"
            value={minutes}
            disabled={loading}
            onChange={(event) => setMinutes(Number(event.target.value))}
          >
            <option value={10}>Last 10 minutes</option>
            <option value={30}>Last 30 minutes</option>
            <option value={180}>Last 3 hours</option>
            <option value={1440}>Last 24 hours</option>
          </select>

          <button type="submit" disabled={loading || !question.trim()}>
            {loading ? 'Asking…' : 'Ask question'}
          </button>
        </div>
      </form>

      {error && (
        <p className="question-error" role="alert">
          {error}
        </p>
      )}

      {answer && (
        <div className="question-answer" aria-live="polite">
          <div className="question-answer-heading">
            <h3>Answer</h3>
            {model && <span>{model}</span>}
          </div>
          <p>{answer}</p>
        </div>
      )}
    </section>
  )
}