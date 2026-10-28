// The run's view, computed from what run.json and the stages' own files say. Pure: no `$`, no I/O.

import type {
  ManuscriptAnswer,
  ManuscriptDecision,
  ManuscriptOutput,
  ManuscriptPhase,
  ManuscriptPhaseId,
  ManuscriptReferees,
  ManuscriptRunView,
  ManuscriptSetting,
  ManuscriptStage,
  ManuscriptStageState,
} from '../../types'

// The parts of run.json (written by runs.py) the view reads.
export type RunRecord = { recorded_at?: string; finished_at?: string }
export type RunArtifact = RunRecord & { path: string; role: string; seat?: string | null; sha256?: string }
export type RunChange = RunRecord & { section: string; path: string }
export type RunSkill = {
  status: string
  reason?: string
  artifacts: RunArtifact[]
  issues: (RunRecord & { kind: string; message: string })[]
  changes: RunChange[]
  commands: RunRecord[]
  // progress records, kept by runs.py from 0.30.0; absent in older runs
  started_at?: string
  finished_at?: string
  // the stage's newest findings.json, counted by `finish`
  counts?: { findings: number; proposals: number; decisions: number }
  // the coordinator's own stages (`runs.py stage`), under manuscript-improve
  stages?: Record<string, RunStep>
}
export type RunStep = { status: string | null; started_at?: string | null; finished_at?: string | null; reason?: string }
export type RunJson = {
  run_id: string
  started_at: string
  context?: {
    effective?: Record<string, string>
    sources?: Record<string, string>
    project_root?: string
    project?: { readers?: string[]; other_models?: string[] }
  }
  inputs?: { original: string; snapshot: string }[]
  skills: Record<string, RunSkill>
  versions?: { new: string }[]
  handover?: { path: string }[]
  // the run stops for the authors (`runs.py wait`), cleared by `resume`
  waiting?: { since?: string; questions?: string[] } | null
  // the stages the run means to run (`start --plan`): skills and the coordinator's own stages
  plan?: string[]
}

// What a stage's newest findings*.json holds, in counts and the decisions only the authors can make.
export type FindingsSummary = {
  findings: number
  proposals: number
  decisions: { id: string; summary: string; section?: string; detail?: string; action?: string }[]
}

// The deliverables the assembly writes, found in the run folder (absolute paths).
export type AssemblyFiles = {
  dashboard: string | null
  word: string | null
  workbook: string | null
  corrected: string | null
  recheck: string | null
  // the newest revision.json's questions for the authors
  questions: { id: string; question: string }[]
}

export type Gathered = {
  runPath: string
  data: RunJson
  findings: Record<string, FindingsSummary>
  files: AssemblyFiles
  referees: ManuscriptReferees | null
  // the manuscript's title, read from the run's snapshot
  title?: string | null
  now: number
}

const REVIEW: [string, string][] = [
  ['manuscript-integrity-check', 'Integrity check'],
  ['manuscript-reference-check', 'References'],
  ['manuscript-reporting-check', 'Reporting'],
  ['manuscript-figures', 'Figures and tables'],
  ['manuscript-policy-fit', 'Policy fit'],
  ['manuscript-journal-select', 'Journal selection'],
  ['manuscript-peer-review', 'Peer review'],
]
// revise is the coordinator's own stage, recorded under manuscript-improve
const EDITING: [string, string][] = [
  ['revise', 'Revise'],
  ['manuscript-prose-edit', 'Prose edit'],
  ['manuscript-deslop', 'Deslop'],
  ['manuscript-story', 'Story'],
  ['manuscript-journal-adapt', 'Journal adaptation'],
]
const ASSEMBLY: [string, string][] = [
  ['manuscript-dashboard', 'Dashboard'],
  ['corrected', 'Corrected version'],
  ['recheck', 'Re-check'],
  ['word', 'Word review'],
  ['workbook', 'Changes workbook'],
  ['handover', 'Handover'],
]
const COORDINATOR = 'manuscript-improve'
const DASHBOARD = 'manuscript-dashboard'
// revise/stage-report.md since 0.33; revise/report.md in earlier runs (and their numbered attempts)
const REVISE_REPORT = /\/revise[^/]*\/(?:stage-)?report[^/]*\.md$/
const STATUS: Record<string, ManuscriptStageState> = {
  completed: 'done',
  reused: 'reused',
  partial: 'partial',
  blocked: 'blocked',
  not_run: 'skipped',
  running: 'running',
}
export const FINISHED: readonly ManuscriptStageState[] = ['done', 'reused', 'partial', 'blocked', 'skipped']

const MEANINGS: Record<string, Record<string, string>> = {
  edits: {
    apply: 'applies every change that needs no decision of yours; listed in the changes workbook',
    conservative: 'applies routine and evidence-backed corrections; proposes the rest',
    propose: 'applies nothing; every change is a proposal you approve',
    none: 'report only; no file of yours changes',
  },
  versions: {
    'in-place': 'edits go into the manuscript file; the earlier version is in git or a backup beside it',
    immutable: 'edits go into a new version file; no earlier file changes',
  },
  reports: {
    file: 'reports saved in the run; headlines in the chat',
    chat: 'reports shown in full in the chat',
    both: 'reports saved in the run and shown in full in the chat',
  },
  keep: {
    everything: 'every intermediate file stays in the run folder',
    results: 'the evidence is packed into evidence.zip at the end',
  },
  peer_review: {
    auto: 'simulated referees run in the full workflow',
    'on-request': 'referees run only when asked',
    off: 'no simulated referees',
  },
}

export function time(stamp: string | undefined | null): number | null {
  if (!stamp) return null
  const ms = Date.parse(stamp)
  return Number.isNaN(ms) ? null : ms
}

function records(skill: RunSkill): number[] {
  const all: (string | undefined)[] = []
  for (const list of [skill.artifacts, skill.issues, skill.changes, skill.commands]) {
    for (const one of list ?? []) all.push(one.recorded_at, one.finished_at)
  }
  return all.map(time).filter((ms): ms is number => ms !== null)
}

// Without a start record, a stage is taken to start at `since` (the run's start for the review stages, which
// start together; the stage before it for an editing stage) or at its first record, whichever is earlier.
function elapsed(
  skill: RunSkill,
  state: ManuscriptStageState,
  now: number,
  since: number | null,
): Pick<ManuscriptStage, 'elapsedMs' | 'isElapsedApprox'> {
  const start = time(skill.started_at)
  const times = records(skill)
  if (start !== null) {
    const finished = time(skill.finished_at)
    const end = state === 'running' ? now : (finished ?? (times.length ? Math.max(...times) : null))
    return { elapsedMs: end === null ? null : end - start, isElapsedApprox: state !== 'running' && finished === null }
  }
  if (times.length === 0) return { elapsedMs: since !== null && state === 'running' ? now - since : null, isElapsedApprox: true }
  const end = state === 'running' ? now : Math.max(...times)
  return { elapsedMs: end - Math.min(...times, since ?? Infinity), isElapsedApprox: true }
}

// Where a stage left off, and the next editing stage is taken to start: revise at its report, a skill at its
// last record.
function endOf(data: RunJson, id: string): number | null {
  if (id === 'revise') {
    const coordinator = data.skills[COORDINATOR]
    return (
      time(coordinator?.stages?.revise?.finished_at) ??
      time(coordinator?.artifacts.filter(item => REVISE_REPORT.test(item.path)).at(-1)?.recorded_at)
    )
  }
  const skill = data.skills[id]
  const times = skill ? records(skill) : []
  return time(skill?.finished_at) ?? (times.length ? Math.max(...times) : null)
}

// One of the coordinator's own stages as `runs.py stage` recorded it: its state and exact times.
function fromStep(g: Gathered, stage: ManuscriptStage, step: RunStep): ManuscriptStage {
  const state = step.status ? (STATUS[step.status] ?? 'running') : 'pending'
  const start = time(step.started_at)
  const end = state === 'running' ? g.now : time(step.finished_at)

  return {
    ...stage,
    state,
    status: step.status,
    elapsedMs: start === null || end === null ? null : end - start,
    isElapsedApprox: false,
    reason: step.reason?.trim() || null,
  }
}

// The newest report a stage registered: stage-report.md (report.md before 0.33), then numbered later attempts.
function newestReport(runPath: string, skill: RunSkill): string | null {
  const reports = skill.artifacts.filter(item => item.role === 'report')
  const last = reports.at(-1)
  return last ? `${runPath}/${last.path}` : null
}

function blank(id: string, label: string, phase: ManuscriptPhaseId): ManuscriptStage {
  return {
    id,
    label,
    phase,
    state: 'pending',
    status: null,
    elapsedMs: null,
    isElapsedApprox: false,
    findings: null,
    proposals: null,
    held: null,
    edits: null,
    report: null,
    reason: null,
  }
}

function fromSkill(
  g: Gathered,
  id: string,
  label: string,
  phase: ManuscriptPhaseId,
  since: number | null = null,
): ManuscriptStage {
  const skill = g.data.skills[id]
  const stage = blank(id, label, phase)
  if (!skill) return stage
  const state = STATUS[skill.status] ?? 'running'
  const found = g.findings[id]
  // the findings file when it was read; else what `finish` counted (a packed run keeps no findings file)
  const counted = found ? { ...found, decisions: found.decisions.length } : skill.counts

  return {
    ...stage,
    state,
    status: skill.status,
    ...elapsed(skill, state, g.now, since),
    findings: counted?.findings ?? null,
    proposals: counted?.proposals ?? null,
    held: counted?.decisions ?? null,
    edits: skill.changes.length > 0 ? skill.changes.length : null,
    report: newestReport(g.runPath, skill),
    reason: skill.reason?.trim() || null,
  }
}

function revise(g: Gathered, edits: string | undefined): ManuscriptStage {
  const stage = blank('revise', 'Revise', 'editing')
  const coordinator = g.data.skills[COORDINATOR]
  if (!coordinator) return stage
  const report = coordinator.artifacts.filter(item => REVISE_REPORT.test(item.path)).at(-1)
  const step = coordinator.stages?.revise
  if (step) {
    const recorded = fromStep(g, stage, step)
    const end = recorded.state === 'running' ? null : time(step.finished_at)
    const changes = coordinator.changes.filter(change => end === null || (time(change.recorded_at) ?? 0) <= end)
    return { ...recorded, edits: changes.length, report: report ? `${g.runPath}/${report.path}` : null }
  }
  if (edits === 'none') return { ...stage, state: 'skipped', reason: 'Report only: nothing is applied.' }
  const brief = coordinator.artifacts.find(item => /(^|\/)stage-brief-revise/.test(item.path))
  const start = time(brief?.recorded_at) ?? time(coordinator.changes[0]?.recorded_at)
  const end = time(report?.recorded_at)
  const changes = coordinator.changes.filter(change => end === null || (time(change.recorded_at) ?? 0) <= end)
  if (!report && !brief && changes.length === 0) return stage

  return {
    ...stage,
    state: report ? 'done' : 'running',
    status: report ? 'completed' : 'running',
    elapsedMs: start === null ? null : (end ?? g.now) - start,
    isElapsedApprox: true,
    edits: changes.length,
    report: report ? `${g.runPath}/${report.path}` : null,
  }
}

function assembly(g: Gathered, id: string, label: string): ManuscriptStage {
  if (id === 'manuscript-dashboard') {
    const stage = fromSkill(g, id, label, 'assembly')
    if (g.files.dashboard && stage.state === 'pending') return { ...stage, state: 'done' }
    if (g.files.dashboard && stage.state === 'running') return { ...stage, state: 'done', status: 'rendered' }
    return stage
  }
  const stage = blank(id, label, 'assembly')
  const file =
    id === 'corrected'
      ? g.files.corrected
      : id === 'recheck'
        ? g.files.recheck
        : id === 'word'
          ? g.files.word
          : id === 'workbook'
            ? g.files.workbook
            : (g.data.handover?.at(-1)?.path ?? null)
  const step = g.data.skills[COORDINATOR]?.stages?.[id]
  if (step) return { ...fromStep(g, stage, step), report: id === 'handover' ? null : file }
  if (id === 'corrected' && g.data.context?.effective?.edits === 'none') {
    return { ...stage, state: 'skipped', reason: 'Report only: no corrected version.' }
  }

  return file ? { ...stage, state: 'done', report: id === 'handover' ? null : file } : stage
}

function phase(stages: ManuscriptStage[], id: ManuscriptPhaseId, label: string): ManuscriptPhase | null {
  const own = stages.filter(stage => stage.phase === id)
  if (own.length === 0) return null

  return { id, label, done: own.filter(stage => FINISHED.includes(stage.state)).length, total: own.length }
}

// "paper1-just-dna-lite" in a folder "v0.6" reads "Paper 1 v0.6".
// Names and folders that say nothing about which manuscript it is, and the numbered heads a name may open with.
const GENERIC = /^(manuscripts?|papers?|main|draft|article|ms|text|index|preprint|submission|docs?|reviews?|latex|tex|src|v?\d+(\.\d+)*)$/i
const VERSION = /^v?\d+(\.\d+)*$/i
const NUMBERED = /^(paper|chapter|manuscript|article|study|part|ms)[-_ ]?(\d+)(?:[-_ ]+(.*))?$/i

// Which manuscript the run is about, short enough for the band: the file's name ("paper1-just-dna-lite" reads
// "Paper 1 just-dna-lite"), the project's folder in place of a name that says nothing ("manuscript"), and the
// project's version folder.
export function runLabel(data: RunJson): string {
  const original = data.inputs?.[0]?.original ?? ''
  const parts = original.split(/[\\/]/).filter(Boolean)
  const stem = (parts.at(-1) ?? '').replace(/\.[^.]+$/, '')
  const head = NUMBERED.exec(stem)
  const numbered = head ? `${head[1]![0]!.toUpperCase()}${head[1]!.slice(1).toLowerCase()} ${head[2]}` : ''
  const rest = head ? (head[3] ?? '') : stem
  const folder = parts.slice(0, -1).reverse().find(part => !GENERIC.test(part) && !part.startsWith('.')) ?? ''
  const name = !rest || GENERIC.test(rest) ? [folder, numbered].filter(Boolean).join(' ') : [numbered, rest].filter(Boolean).join(' ')
  const version = (data.context?.project_root ?? '').split(/[\\/]/).at(-1) ?? ''

  return `${name || stem || data.run_id}${VERSION.test(version) ? ` ${version}` : ''}`
}

// The manuscript's title from its text: LaTeX's \title{} (else a class's own \...title{}), else a Markdown
// file's front matter `title:` or its first heading; markup and comments taken out.
export function manuscriptTitle(text: string, name: string): string | null {
  let found: string | undefined
  if (/\.tex$/i.test(name)) {
    const braced = '\\s*(?:\\[[^\\]]*\\])?\\s*\\{((?:[^{}]|\\{[^{}]*\\})*)\\}'
    found = new RegExp(`\\\\title${braced}`).exec(text)?.[1] ?? new RegExp(`\\\\[A-Za-z@]+title${braced}`).exec(text)?.[1]
  } else {
    const front = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)?.[1] ?? ''
    found = /^title:\s*["']?(.+?)["']?\s*$/m.exec(front)?.[1] ?? /^#\s+(.+)$/m.exec(text)?.[1]
  }
  const title = (found ?? '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\\\\|\\[A-Za-z]+\*?/g, ' ')
    .replace(/[{}*`]/g, '')
    .replace(/\s+/g, ' ')
    .trim()

  return title || null
}

function settings(data: RunJson): ManuscriptSetting[] {
  const effective = data.context?.effective ?? {}
  const sources = data.context?.sources ?? {}
  const list: ManuscriptSetting[] = Object.entries(effective).map(([key, value]) => ({
    key,
    value,
    source: sources[key] ?? null,
    meaning: MEANINGS[key]?.[value] ?? '',
  }))
  const project = data.context?.project
  if (project?.readers?.length) {
    list.push({ key: 'readers', value: project.readers.map(r => r.split(':')[0]!.trim()).join(', '), source: 'project', meaning: 'the story panel' })
  }
  if (project?.other_models?.length) {
    list.push({ key: 'other models', value: project.other_models.join(', '), source: 'project', meaning: 'panels also read on these' })
  }

  return list
}

function outputs(g: Gathered): ManuscriptOutput[] {
  const list: ManuscriptOutput[] = [{ key: 'index', label: 'Run index', path: `${g.runPath}/README.md` }]
  const edits = g.data.context?.effective?.edits
  const manuscript = g.data.versions?.at(-1)?.new ?? g.data.inputs?.[0]?.original
  if (manuscript && edits !== 'none') list.push({ key: 'manuscript', label: 'Manuscript (edited live)', path: manuscript })
  const latest = Object.values(g.data.skills)
    .flatMap(skill => skill.changes)
    .sort((a, b) => (time(a.recorded_at) ?? 0) - (time(b.recorded_at) ?? 0))
    .at(-1)
  if (latest) list.push({ key: 'latest-edit', label: `Latest edit (${latest.section})`, path: `${g.runPath}/${latest.path}` })
  for (const [key, label, path] of [
    ['dashboard', 'Dashboard', g.files.dashboard],
    ['corrected', 'Corrected version', g.files.corrected],
    ['word', 'Word review', g.files.word],
    ['workbook', 'Changes workbook', g.files.workbook],
  ] as const) {
    if (path) list.push({ key, label, path })
  }

  return list
}

function decisions(g: Gathered, stages: ManuscriptStage[]): ManuscriptDecision[] {
  const label = new Map(stages.map(stage => [stage.id, stage.label]))
  const list: ManuscriptDecision[] = []
  // once the dashboard has adjudicated the stages' findings, its inventory is the one list without repeats
  const inventory = g.findings[DASHBOARD]
  const sources = inventory ? [[DASHBOARD, inventory] as const] : Object.entries(g.findings)
  for (const [skill, found] of sources) {
    for (const one of found.decisions) {
      list.push({
        id: one.id,
        stage: label.get(skill) ?? skill,
        summary: one.summary,
        section: one.section || null,
        detail: one.detail || null,
        action: one.action || null,
      })
    }
  }
  for (const one of g.files.questions) {
    list.push({ id: one.id, stage: 'Corrected version', summary: one.question, section: null, detail: null, action: null })
  }

  return list
}

// Each decision's address, the same across refreshes: its run, stage and id, made unique where two share them.
export function decisionKeys(runId: string, list: ManuscriptDecision[]): string[] {
  const seen = new Set<string>()
  return list.map((one, n) => {
    let key = `${runId}:${one.stage}:${one.id || n}`
    if (seen.has(key)) key = `${key}#${n}`
    seen.add(key)
    return key
  })
}

const where = (one: ManuscriptDecision) => `${one.id}${one.section ? ` (${one.section})` : ''}`

// The one message the Decisions pane sends with the answers not sent yet, in the person's words: what to go
// ahead with and what to leave, each named so Claude finds it in the run without the pane.
export function answersMessage(view: ManuscriptRunView, answers: Record<string, ManuscriptAnswer>): string {
  const keys = decisionKeys(view.runId, view.decisions)
  const chosen = (choice: ManuscriptAnswer['choice']) =>
    view.decisions.filter((_, n) => answers[keys[n]!]?.choice === choice && !answers[keys[n]!]!.isSent)
  const ahead = chosen('go-ahead')
  const leave = chosen('leave')
  const lines = [`My answers to the decisions the ${view.label} manuscript run left for me (run folder ${view.runPath}):`]
  if (ahead.length) {
    lines.push('', 'Go ahead:')
    for (const one of ahead) lines.push(`- ${where(one)}: ${one.summary}${one.action ? ` Suggested: ${one.action}` : ''}`)
  }
  if (leave.length) {
    lines.push('', 'Leave as it is:')
    for (const one of leave) lines.push(`- ${where(one)}: ${one.summary}`)
  }
  lines.push(
    '',
    ahead.length
      ? 'Make the go-ahead changes in the manuscript, taking the option you recommend where a suggestion offers a choice, and tell me which need something only I can do. Change nothing for the ones to leave.'
      : 'Change nothing for these.',
  )

  return lines.join('\n')
}

// What "Write answer" puts in the prompt box: the decision, named, for the person to finish in their own words.
export function answerDraft(view: ManuscriptRunView, one: ManuscriptDecision): string {
  return `On decision ${where(one)} of the ${view.label} manuscript run (${view.runPath}), "${one.summary}": `
}

export function buildView(g: Gathered): ManuscriptRunView {
  const { data } = g
  const edits = data.context?.effective?.edits
  const isFull = COORDINATOR in data.skills
  const known = new Set([...REVIEW, ...EDITING, ...ASSEMBLY].map(([id]) => id).concat(COORDINATOR))

  // with a plan, the stages it names and any the run recorded besides; without one, the full workflow's
  const plan = data.plan?.length ? new Set(data.plan) : null
  const steps = data.skills[COORDINATOR]?.stages ?? {}
  const isNamed = (id: string) => id in data.skills || id in steps || Boolean(plan?.has(id))
  const started = time(data.started_at)
  const review = REVIEW.filter(([id]) => isNamed(id)).map(([id, label]) => fromSkill(g, id, label, 'review', started))
  const others = [...new Set([...Object.keys(data.skills), ...(data.plan ?? [])])]
    .filter(id => !known.has(id))
    .map(id => fromSkill(g, id, id.replace(/^manuscript-/, '').replaceAll('-', ' '), 'review', started))
  // the editing stages run one after another, each from where the one before it left off
  let since: number | null = null
  const editing = EDITING.filter(([id]) => (plan ? isNamed(id) : isFull || id in data.skills)).map(([id, label]) => {
    const stage = id === 'revise' ? revise(g, edits) : fromSkill(g, id, label, 'editing', since)
    if (stage.state !== 'pending') since = endOf(data, id) ?? since
    return stage
  })
  const hasDashboard = plan ? isNamed(DASHBOARD) : isFull || DASHBOARD in data.skills
  // the Word review and the changes workbook are the dashboard stage's files, not stages of a plan
  const built = ASSEMBLY.filter(([id]) =>
    plan ? (id === 'word' || id === 'workbook' ? hasDashboard : isNamed(id)) : hasDashboard,
  ).map(([id, label]) => assembly(g, id, label))
  const stages = [...review, ...others, ...editing, ...built]

  const coordinator = data.skills[COORDINATOR]
  const isFinished = coordinator
    ? FINISHED.includes(STATUS[coordinator.status] ?? 'running') || (data.handover?.length ?? 0) > 0
    : Object.values(data.skills).every(skill => FINISHED.includes(STATUS[skill.status] ?? 'running'))
  // nothing records "started" yet: the first stage still to do after the finished ones is the next
  if (!isFinished && !stages.some(stage => stage.phase !== 'review' && stage.state === 'running')) {
    const next = stages.find(stage => stage.phase !== 'review' && stage.state === 'pending')
    if (next) next.state = 'next'
  }
  const running = stages.filter(stage => stage.state === 'running')
  const current = (running.find(stage => stage.phase !== 'review') ?? running[0] ?? stages.find(s => s.state === 'next'))?.label ?? null

  const list = decisions(g, stages)
  // the dashboard's inventory once it exists; before, each stage's own count, read or recorded by `finish`
  const inventory = g.findings[DASHBOARD]
  const held =
    (inventory
      ? inventory.decisions.length
      : stages.filter(stage => stage.id !== DASHBOARD).reduce((sum, stage) => sum + (stage.held ?? 0), 0)) +
    g.files.questions.length
  const times = Object.values(data.skills).flatMap(records)

  return {
    runPath: g.runPath,
    runId: data.run_id,
    label: runLabel(data),
    title: g.title ?? null,
    startedAt: time(data.started_at),
    lastRecordAt: times.length ? Math.max(...times) : null,
    stages,
    phases: [
      phase(stages, 'review', 'Review'),
      phase(stages, 'editing', 'Editing'),
      phase(stages, 'assembly', 'Assembly'),
    ].filter((one): one is ManuscriptPhase => one !== null),
    settings: settings(data),
    outputs: outputs(g),
    referees: g.referees,
    decisions: list,
    waitingFor: data.waiting
      ? { since: time(data.waiting.since), questions: data.waiting.questions ?? [] }
      : null,
    isWaiting: Boolean(data.waiting) || (isFinished && list.length > 0),
    isPlanned: plan !== null,
    isFinished,
    current,
    editsApplied: Object.values(data.skills).reduce((sum, skill) => sum + skill.changes.length, 0),
    held,
    dashboard: g.files.dashboard,
  }
}

// A venue id as the journal spells its name: iscience -> iScience, jamia-open -> JAMIA Open.
const SPELLED: Record<string, string> = { iscience: 'iScience', jamia: 'JAMIA', plos: 'PLOS', bmc: 'BMC', nar: 'NAR', elife: 'eLife', peerj: 'PeerJ', gigascience: 'GigaScience', nargab: 'NARGAB' }
export function journal(venue: string): string {
  return venue
    .split(/[-_ ]+/)
    .map(word => SPELLED[word.toLowerCase()] ?? `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(' ')
}

// Seats by venues, from the peer-review stage's reports: each seat's recommendation per journal.
export function refereeGrid(
  reports: { seat?: string; recommendations?: { venue?: string; recommendation?: string }[] }[],
): ManuscriptReferees | null {
  const venues: string[] = []
  for (const report of reports) {
    for (const one of report.recommendations ?? []) {
      if (one.venue && !venues.includes(one.venue)) venues.push(one.venue)
    }
  }
  if (venues.length === 0) return null
  const seats = reports
    .filter(report => report.seat)
    .map(report => ({
      seat: report.seat!,
      cells: venues.map(venue => {
        const said = report.recommendations?.find(one => one.venue === venue)?.recommendation
        return said ? said.replace(/-revision$/, '') : null
      }),
    }))

  return { venues: venues.map(journal), seats }
}

// One findings*.json, counted: findings, proposals, and the findings only the authors can decide.
export function summarizeFindings(parsed: unknown): FindingsSummary | null {
  if (typeof parsed !== 'object' || parsed === null) return null
  const body = parsed as { findings?: unknown; changes?: unknown }
  if (!Array.isArray(body.findings)) return null
  type Finding = { id?: string; summary?: string; section?: string; detail?: string; action?: string; decision?: boolean }
  const findings = body.findings as Finding[]
  const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value : undefined)

  return {
    findings: findings.length,
    proposals: Array.isArray(body.changes) ? body.changes.length : 0,
    decisions: findings
      .filter(one => one.decision === true)
      .map(one => ({
        id: String(one.id ?? ''),
        summary: String(one.summary ?? ''),
        section: text(one.section),
        detail: text(one.detail),
        action: text(one.action),
      })),
  }
}

export function duration(ms: number | null, isApprox = false): string {
  if (ms === null || ms < 0) return ''
  const minutes = Math.round(ms / 60000)
  const text = minutes < 1 ? '<1m' : minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`

  return isApprox ? `~${text}` : text
}

export function counts(stage: ManuscriptStage): string {
  const parts: string[] = []
  if (stage.findings !== null) parts.push(`${stage.findings} findings`)
  if (stage.proposals) parts.push(`${stage.proposals} proposals`)
  if (stage.edits) parts.push(`${stage.edits} edits`)
  if (stage.held) parts.push(`${stage.held} held`)

  return parts.join(' · ')
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// `open`: the decisions the authors have not answered yet in the Decisions pane; all of them when not given.
export function statusLine(view: ManuscriptRunView, open = view.decisions.length): string {
  const done = view.stages.filter(stage => FINISHED.includes(stage.state)).length
  const parts = [view.label, `${done} of ${view.stages.length} stages`]
  if (view.waitingFor) parts.push(`waits for your answer (${plural(view.waitingFor.questions.length, 'question')})`)
  else if (view.isWaiting) parts.push(open > 0 ? `${open} decisions wait for you` : 'decisions answered')
  else if (view.isFinished) parts.push('finished')
  else if (view.current) {
    const running = view.stages.some(stage => stage.label === view.current && stage.state === 'running')
    parts.push(`${view.current.toLowerCase()} ${running ? 'running' : 'next'}`)
  }
  parts.push(`${view.editsApplied} edits applied`, `${view.held} held`)

  return parts.join(' · ')
}
