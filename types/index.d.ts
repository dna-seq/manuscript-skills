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

export type ManuscriptDecision = { id: string; stage: string; summary: string }

export type ManuscriptRunView = {
  runPath: string
  runId: string
  label: string
  startedAt: number | null
  // time of the newest record in the run
  lastRecordAt: number | null
  stages: ManuscriptStage[]
  phases: ManuscriptPhase[]
  settings: ManuscriptSetting[]
  outputs: ManuscriptOutput[]
  referees: ManuscriptReferees | null
  decisions: ManuscriptDecision[]
  // the run finished and decisions wait for the authors, or the run recorded that it waits
  isWaiting: boolean
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
      isDecisionsFirst: boolean
      // the waiting signature the person hid the band for; a new decision shows it again
      hiddenBand: string | null
    }
  }
}
