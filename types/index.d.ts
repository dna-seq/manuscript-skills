// What the manuscript-skills progress pane, band and status line draw, computed from a run folder's run.json.

export type ManuscriptStageState =
  | 'done'
  | 'reused'
  | 'partial'
  | 'blocked'
  | 'skipped'
  | 'running'
  | 'next'
  | 'pending'

export type ManuscriptPhaseId = 'review' | 'editing' | 'assembly'

export type ManuscriptStage = {
  id: string
  label: string
  phase: ManuscriptPhaseId
  state: ManuscriptStageState
  // run.json's own status word, when the stage has an entry
  status: string | null
  elapsedMs: number | null
  // true when elapsed time is read from the first and last records, not a start and finish record
  isElapsedApprox: boolean
  findings: number | null
  proposals: number | null
  held: number | null
  edits: number | null
  // absolute path of the stage's newest report, when it has one
  report: string | null
  reason: string | null
}

export type ManuscriptPhase = {
  id: ManuscriptPhaseId
  label: string
  done: number
  total: number
}

export type ManuscriptReferees = {
  venues: string[]
  seats: { seat: string; cells: (string | null)[] }[]
}

export type ManuscriptSetting = {
  key: string
  value: string
  source: string | null
  meaning: string
}

export type ManuscriptOutput = { key: string; label: string; path: string }

export type ManuscriptDecision = {
  id: string
  stage: string
  summary: string
  // what the finding says beyond its summary, when it says it: where, why, and what the authors are asked
  section: string | null
  detail: string | null
  action: string | null
}

// The authors' answer to one decision, given in the Decisions pane: go ahead as it suggests, leave the text as it
// is, or their own words put in the prompt box. The first two wait to go to Claude together in one message.
export type ManuscriptAnswer = {
  choice: 'go-ahead' | 'leave' | 'written'
  isSent: boolean
}

export type ManuscriptRunView = {
  runPath: string
  runId: string
  // which manuscript: its file's name, with the project's folder where the name alone says nothing ("manuscript")
  label: string
  // the manuscript's own title, from the run's snapshot of it
  title: string | null
  startedAt: number | null
  // time of the newest record in the run
  lastRecordAt: number | null
  stages: ManuscriptStage[]
  phases: ManuscriptPhase[]
  settings: ManuscriptSetting[]
  outputs: ManuscriptOutput[]
  referees: ManuscriptReferees | null
  decisions: ManuscriptDecision[]
  // what the run stopped for (`runs.py wait`) and since when; null while it goes on
  waitingFor: { since: number | null; questions: string[] } | null
  // the run stopped for an answer, or it finished and decisions wait for the authors
  isWaiting: boolean
  // the stages come from the run's plan (`start --plan`), not the full workflow's list
  isPlanned: boolean
  isFinished: boolean
  current: string | null
  editsApplied: number
  held: number
  dashboard: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'manuscript-skills': {
      view: ManuscriptRunView | null
      // why no run is shown: none found yet, or the run.json could not be read
      problem: string | null
      // the decisions unfolded to their detail and answer buttons, as `runId:stage:id`
      unfoldedDecisions: string[]
      // the authors' answers, by the same `runId:stage:id`
      answers: Record<string, ManuscriptAnswer>
      // the waiting signature the person hid the band for; a new decision shows it again
      hiddenBand: string | null
    }
  }
}
