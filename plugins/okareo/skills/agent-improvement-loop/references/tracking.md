# Tracking the loop — ledger + dashboard

Loaded at the record step. The point of the loop is improvement you can *see*,
which needs two surfaces: a **local ledger** that holds the narrative (the
"why" lives nowhere in Okareo) and an **Okareo dashboard** that mirrors the
metric trend for sharing. They join on the run id.

## Why two surfaces

The Okareo backend stores the numbers — per-run scores, latency, turn counts.
It does **not** store the reasoning: the hypothesis, the named root cause, the
Change Spec, or the verdict. That narrative is what makes a trend legible
("latency fixed first, then content") and what lets you audit, in supervised
mode, that the loop made the right kinds of changes. So the ledger is the
source of truth for the story; the dashboard is the shareable mirror of the
metrics.

## The local ledger

Per agent, append one record per cycle to `improvement-log/<agent>/cycles.jsonl`,
and render a human-readable trend to `improvement-log/<agent>/README.md`.

```json
{
  "cycle": 1,
  "run_id": "665a9245-...",
  "run_name": "VAPI Docs Agent - Voice Sim Q&A - Run 8",
  "timestamp": "2026-06-03T18:41:45Z",
  "hypothesis": "latency is gating the later objectives",
  "root_cause": "latency-bound coverage",
  "change_spec": { "...": "see references/edit-delegation.md" },
  "checks_used": ["result_completed", "Improvement Analysis", "Pronunciation (Audio)"],
  "metrics_before": { "result_completed": 1.0, "avg_turn_latency_ms": 41038, "total_turn_count": 4 },
  "metrics_after":  { "result_completed": 1.0, "avg_turn_latency_ms": 22400, "total_turn_count": 5 },
  "deltas":         { "avg_turn_latency_ms": -18638, "total_turn_count": 1 },
  "analysis_verdict": "Partially",
  "verdict": "partial"
}
```

Notes on the fields:

- The metric blocks mirror the run record's aggregate scores, keyed by check
  name plus the latency/turn aggregates — the real shape returned by
  `get_test_run_results`.
- **Record `analysis_verdict` (read from the analysis explanation text)
  separately from the numeric check score.** They disagree; the text is the
  honest verdict and is what the trend should show.
- `verdict` is the loop's call: `fixed` / `partial` / `regressed` / `no-change`.

The ledger also makes the loop resumable — a later session can read it to see
where the agent stands without re-deriving everything.

## The Okareo dashboard

Mirror the metric trend into Okareo so it is shareable in the app. Pull the
cross-run metrics with `query_analytics` and persist the view with
`save_dashboard`: one panel per metric that matters (outcome, key objective
coverage, latency, turn count, completion), across the loop's runs, linked back
to each run. The dashboard carries metrics only — it is the ledger that makes
those metrics mean something, so keep both.

## Rendering the trend

The report's trend table renders from the ledger: columns are runs (baseline +
each cycle), rows are the metrics that moved. Lead with the net change across
the whole loop (coverage, latency, regressions caught), then the per-cycle
detail. A loop that does not end in a visible trend was not tracked.
</content>
