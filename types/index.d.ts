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
  // as the dashboard's To-do tab lists it: a decision only the authors can make, or a question the corrected
  // version asks them
  kind: 'decision' | 'question'
  stage: string
  summary: string
  // what the finding says beyond its summary, when it says it: where, why, and what the authors are asked
  section: string | null
  detail: string | null
  action: string | null
  // the passage it is about and the findings behind it, which a mark copies
  quote: string | null
  findingIds: string[]
  // the authors' mark on it for this run in STEM.todo.json, made in the dashboard's To-do tab or in the pane
  mark: { mark: 'approved' | 'redundant'; reason: string; markedAt: string } | null
}

// One mark in STEM.todo.json beside the manuscript, the file the dashboard's To-do tab saves and the next run
// reads (data-contract.md, "To-do"; dashboard.py `Mark`): approved or redundant, on one item of one run, with what
// the item said.
export type ManuscriptTodoMark = {
  run_id: string
  kind: 'decision' | 'question' | 'proposal' | 'problem'
  id: string
  mark: 'approved' | 'redundant'
  reason: string
  marked_at: string
  summary: string
  section: string
  category: string
  quote: string | null
  action: string
  before: string | null
  after: string | null
  anchor: string | null
  finding_ids: string[]
}

// The authors' answer to one decision, given in the Decisions pane: go ahead as it suggests, leave the text as it
// is, their own words put in the prompt box, or a new session of its own that asks them about it. The first two
// wait to go to Claude together in one message, and on a decision are marked in STEM.todo.json at once.
export type ManuscriptAnswer = {
  choice: 'go-ahead' | 'leave' | 'written' | 'session'
  isSent: boolean
  // when the pane marked it in STEM.todo.json, and the mark it replaced there, which Undo puts back
  markedAt?: string
  replaced?: ManuscriptTodoMark | null
}

export type ManuscriptRunView = {
  runPath: string
  runId: string
  // which manuscript: the paper's own name from its title ("Just-DNA-Lite"), else its file's name, with the
  // project's folder where the name alone says nothing ("manuscript"); then the project's version folder
  label: string
  // the manuscript's own title, from the run's snapshot of it
  title: string | null
  // the manuscript file the run works on: its newest version, else the first input
  manuscript: string | null
  startedAt: number | null
  // time of the newest record in the run
  lastRecordAt: number | null
  stages: ManuscriptStage[]
  phases: ManuscriptPhase[]
  settings: ManuscriptSetting[]
  outputs: ManuscriptOutput[]
  referees: ManuscriptReferees | null
  decisions: ManuscriptDecision[]
  // STEM.todo.json beside the manuscript and the manuscript's file name, once the dashboard's inventory lists the
  // decisions: the pane and the To-do tab then list the same ones, and keep the authors' marks there
  todo: { path: string; manuscript: string } | null
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
