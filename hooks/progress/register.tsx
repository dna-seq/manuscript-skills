// A manuscript-skills run, watched read-only: a status line, a "Manuscript run" pane, a "Decisions" pane and a
// band when the authors have decisions to make, toasts as stages finish and /manuscript-status. Reads run.json
// and the stages' own report files; writes nothing in the run folder. The authors' answers go to Claude as a
// message of theirs, which the session acts on; go ahead and leave as is on a decision are also marked in
// STEM.todo.json beside the manuscript, the file the dashboard's To-do tab shares and the next run reads.

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type {
  ManuscriptAnswer,
  ManuscriptDecision,
  ManuscriptReferees,
  ManuscriptRunView,
  ManuscriptStage,
  ManuscriptTodoMark,
} from '../../types'
import {
  answerDraft,
  answersMessage,
  buildView,
  counts,
  decisionKeys,
  duration,
  FINISHED,
  manuscriptTitle,
  marksFile,
  parseMarks,
  refereeGrid,
  sessionRequest,
  statusLine,
  summarizeFindings,
  todoMark,
  withMark,
} from './model'
import type { AssemblyFiles, FindingsSummary, MarksFile, RunJson } from './model'

const PANE = 'manuscript-run'
const TITLE = 'Manuscript run'
const DECISIONS = 'manuscript-decisions'
const REFRESH_MS = 15_000
const RUN_ID = /\d{8}T\d{6}Z-[0-9a-f]{8}/
const PROJECT_FILE = '.manuscript-skills.yaml'
// Stages that write no findings.json of their own (runs.py NO_FINDINGS); the dashboard's inventory is read
const NO_FINDINGS = new Set(['manuscript-improve', 'manuscript-other-models', 'manuscript-mark-people'])

const view = atom({ plugin: 'manuscript-skills', key: 'view' } as const, null)
const problem = atom({ plugin: 'manuscript-skills', key: 'problem' } as const, null)
const hiddenBand = atom({ plugin: 'manuscript-skills', key: 'hiddenBand' } as const, null)
const unfoldedDecisions = atom({ plugin: 'manuscript-skills', key: 'unfoldedDecisions' } as const, [])
const answers = atom({ plugin: 'manuscript-skills', key: 'answers' } as const, {})

type $ = EngineInterface

const join = (dir: string, name: string) => `${dir.replace(/[\\/]+$/, '')}/${name}`
const parent = (path: string) => path.replace(/[\\/]+$/, '').replace(/[\\/][^\\/]*$/, '') || '/'
const stampOf = (stat: { mtimeMs: number; size: number }) => `${stat.mtimeMs}:${stat.size}`

async function readJson($: $, path: string): Promise<unknown> {
  try {
    return JSON.parse(await $.fs.read(path))
  } catch {
    return null
  }
}

async function list($: $, dir: string) {
  return $.fs.list(dir).catch(() => [])
}

// The output folder a project file names (`output_dir`, `reviews` when unset), as an absolute path.
async function outputDir($: $, projectDir: string): Promise<string> {
  const text = await $.fs.read(join(projectDir, PROJECT_FILE)).catch(() => '')
  const named = /^output_dir:\s*['"]?([^'"#\n]+?)['"]?\s*$/m.exec(text)?.[1] ?? 'reviews'

  return /^([\\/]|[A-Za-z]:)/.test(named) ? named : join(projectDir, named)
}

// The newest run folder under an output folder: run ids start with their UTC time, so they sort by name.
async function newestRun($: $, dir: string): Promise<string | null> {
  const runs = (await list($, dir))
    .filter(entry => entry.kind === 'dir' && new RegExp(`^${RUN_ID.source}$`).test(entry.name))
    .map(entry => entry.name)
    .sort()
    .reverse()
  for (const name of runs) {
    if (await $.fs.exists(join(join(dir, name), 'run.json'))) return join(dir, name)
  }

  return null
}

// A run from what the person names: a run folder or its run.json, a project folder or a file in it, or an
// output folder; the newest run there.
async function locate($: $, given: string): Promise<string | null> {
  const home = (await $.env.get('HOME')) ?? ''
  const path = given.trim().replace(/^~(?=[\\/]|$)/, home).replace(/[\\/]+$/, '').replace(/[\\/]run\.json$/, '')
  const id = RUN_ID.exec(path)
  if (id) {
    const run = path.slice(0, id.index + id[0].length)
    if (await $.fs.exists(join(run, 'run.json'))) return run
  }
  if (await $.fs.exists(join(path, 'run.json'))) return path
  let dir = path
  for (let depth = 0; depth < 8; depth += 1) {
    if (await $.fs.exists(join(dir, PROJECT_FILE))) return newestRun($, await outputDir($, dir))
    const up = parent(dir)
    if (up === dir) break
    dir = up
  }

  return newestRun($, path)
}

// Watching one run at a time; the module's own memory, rebuilt after a reload from $.store and run.json.
let runPath: string | null = null
let runStamp = ''
let data: RunJson | null = null
let findings: Record<string, FindingsSummary> = {}
let referees: ManuscriptReferees | null = null
let refereesFrom = ''
let title: string | null = null
let titleFrom = ''
let files: AssemblyFiles = { dashboard: null, word: null, workbook: null, corrected: null, recheck: null, questions: [] }
let filesStamp = ''
let marks: ManuscriptTodoMark[] = []
let marksStamp = ''
let refreshing: Promise<void> | null = null
let opener: string[] | null = null
// The run a runs.py call opened the pane for: opened unasked once per run, not again after the person closes it
let offered: string | null = null

async function choose($: $, run: string): Promise<void> {
  if (run === runPath) return
  runPath = run
  runStamp = ''
  filesStamp = ''
  marks = []
  marksStamp = ''
  data = null
  findings = {}
  referees = null
  refereesFrom = ''
  title = null
  titleFrom = ''
  await $.store.set('runPath', run)
}

// The manuscript's title, from the run's snapshot of its first input; read once per snapshot.
async function readTitle($: $, run: string, json: RunJson): Promise<void> {
  const snapshot = json.inputs?.[0]?.snapshot
  if (!snapshot || snapshot === titleFrom) return
  titleFrom = snapshot
  const text = await $.fs.read(join(run, snapshot)).catch(() => '')
  title = manuscriptTitle(text, snapshot)
}

// A stage's newest findings*.json: findings.json, then findings.2.json and on, as runs.py numbers attempts.
async function newestFindings($: $, run: string, skill: string): Promise<string | null> {
  let last: string | null = null
  for (let attempt = 1; attempt < 10; attempt += 1) {
    const path = join(join(run, skill), attempt === 1 ? 'findings.json' : `findings.${attempt}.json`)
    if (!(await $.fs.exists(path))) break
    last = path
  }

  return last
}

async function readFindings($: $, run: string, json: RunJson): Promise<Record<string, FindingsSummary>> {
  const found: Record<string, FindingsSummary> = {}
  for (const skill of Object.keys(json.skills)) {
    if (NO_FINDINGS.has(skill)) continue
    const path = await newestFindings($, run, skill)
    const summary = path ? summarizeFindings(await readJson($, path)) : null
    if (summary) found[skill] = summary
  }

  return found
}

// The referees' recommendations: the adjudicated file holds every seat's report; else each referee's own.
async function readReferees($: $, run: string, json: RunJson): Promise<void> {
  const review = json.skills['manuscript-peer-review']
  if (!review) return
  const adjudication = review.artifacts.filter(item => item.role === 'adjudication').at(-1)
  const seats = review.artifacts.filter(item => item.role === 'referee')
  const from = [adjudication, ...seats].map(item => item?.sha256 ?? '').join(',')
  if (from === refereesFrom) return
  refereesFrom = from
  type Report = { seat?: string; recommendations?: { venue?: string; recommendation?: string }[] }
  const whole = adjudication ? ((await readJson($, join(run, adjudication.path))) as { reports?: Report[] } | null) : null
  let reports = whole?.reports ?? []
  if (reports.length === 0) {
    for (const seat of seats) {
      const one = (await readJson($, join(run, seat.path))) as { report?: Report } | null
      if (one?.report) reports = [...reports, { seat: seat.seat ?? one.report.seat, ...one.report }]
    }
  }
  referees = refereeGrid(reports)
}

// The newest of the files a pattern names, by modification time, in a folder and its numbered attempt folders.
async function newest($: $, dir: string, folders: RegExp, name: RegExp) {
  const top = await list($, dir)
  const found = top.filter(entry => entry.kind === 'file' && name.test(entry.name)).map(entry => ({ ...entry, path: join(dir, entry.name) }))
  for (const sub of top.filter(entry => entry.kind === 'dir' && folders.test(entry.name))) {
    for (const entry of await list($, join(dir, sub.name))) {
      if (entry.kind === 'file' && name.test(entry.name)) found.push({ ...entry, path: join(join(dir, sub.name), entry.name) })
    }
  }

  return found.sort((a, b) => b.mtimeMs - a.mtimeMs)[0] ?? null
}

// What the end of the run writes, found by the names runs.py itself looks for (DASHBOARD, WORD, WORKBOOK,
// CORRECTED) and the re-check beside the revision.
async function readFiles($: $, run: string): Promise<void> {
  const board = join(run, 'manuscript-dashboard')
  const improve = join(run, 'manuscript-improve')
  const dashboard = await newest($, board, /^dashboard/, /manuscript-dashboard.*\.html$/)
  const word = await newest($, board, /^dashboard/, /\.docx$/)
  const workbook = await newest($, board, /^dashboard/, /changes.*\.xlsx$/)
  const corrected = await newest($, improve, /^revision(\.\d+)?$/, /^proposed/)
  const recheck = await newest($, improve, /^$/, /^recheck(\.\d+)?\.json$/)
  const revision = await newest($, improve, /^revision(\.\d+)?$/, /^revision\.json$/)
  const stamp = [dashboard, word, workbook, corrected, recheck, revision].map(one => (one ? `${one.path}@${stampOf(one)}` : '-')).join('|')
  if (stamp === filesStamp) return
  filesStamp = stamp
  type Revision = { comments?: { ids?: string[]; question?: string }[] }
  const record = revision ? ((await readJson($, revision.path)) as Revision | null) : null
  files = {
    dashboard: dashboard?.path ?? null,
    word: word?.path ?? null,
    workbook: workbook?.path ?? null,
    corrected: corrected?.path ?? null,
    recheck: recheck?.path ?? null,
    questions: (record?.comments ?? []).map(one => ({ id: one.ids?.[0] ?? '', question: one.question ?? '' })),
  }
}

// The authors' marks in STEM.todo.json, re-read when the file changes; none while there is no file, or the dashboard
// has not listed the decisions yet. A file caught mid-save is read again at the next tick, its marks kept meanwhile.
async function readMarks($: $, path: string | null): Promise<void> {
  const stat = path ? await $.fs.stat(path).catch(() => null) : null
  const stamp = path && stat ? `${path}@${stampOf(stat)}` : '-'
  if (stamp === marksStamp) return
  if (!path || !stat) {
    marks = []
    marksStamp = stamp
    return
  }
  const file = parseMarks(await readJson($, path))
  if (!file) return
  marks = file.marks
  marksStamp = stamp
}

const fileName = (path: string) => path.split(/[\\/]/).at(-1) ?? path

// Changes the marks file as `edit` says, keeping every other mark in it: read afresh just before it is written, so
// a mark the To-do tab saved meanwhile stays. `edit` answers null to leave the file as it is. A file that is there
// but does not read as marks is never written over. Says whether the file holds the change.
async function editMarks($: $, path: string, edit: (file: MarksFile | null) => MarksFile | null): Promise<boolean> {
  const isThere = await $.fs.exists(path).catch(() => false)
  const file = isThere ? parseMarks(await readJson($, path)) : null
  if (isThere && !file) {
    $.ui.toast(`${fileName(path)} does not read as the To-do tab's marks, so the answer is kept in this session only.`)
    return false
  }
  const next = edit(file)
  if (!next) return true
  const isWritten = await $.fs.write(path, `${JSON.stringify(next, null, 2)}\n`).then(
    () => true,
    () => false,
  )
  if (!isWritten) {
    $.ui.toast(`${fileName(path)} could not be written, so the answer is kept in this session only.`)
    return false
  }
  marks = next.marks
  marksStamp = ''

  return true
}

const MARK: Partial<Record<ManuscriptAnswer['choice'], ManuscriptTodoMark['mark']>> = { 'go-ahead': 'approved', leave: 'redundant' }

// The person's answer to one decision, in the session's answers and, for go ahead and leave as is on a decision, in
// the marks file as approved or redundant, its reason kept. An answer that replaces or undoes one the pane marked
// takes that mark back, putting back what it replaced, unless the To-do tab has changed the mark since.
async function setAnswer(
  $: $,
  v: ManuscriptRunView,
  one: ManuscriptDecision,
  key: string,
  choice: ManuscriptAnswer['choice'] | null,
  isSent = choice === 'written',
): Promise<void> {
  const before = (await read($, answers))[key]
  const mark = choice ? MARK[choice] : undefined
  let filed: Pick<ManuscriptAnswer, 'markedAt' | 'replaced'> = {}
  if (v.todo && one.kind === 'decision' && (mark || before?.markedAt)) {
    const todo = v.todo
    const at = new Date(await $.clock.now()).toISOString()
    const item = { run_id: v.runId, kind: one.kind, id: one.id }
    let replaced: ManuscriptTodoMark | null = before?.markedAt ? (before.replaced ?? null) : null
    const isFiled = await editMarks($, todo.path, file => {
      const was = file?.marks.find(m => m.run_id === item.run_id && m.kind === item.kind && m.id === item.id) ?? null
      if (!before?.markedAt) replaced = was
      if (mark) return withMark(file, todo.manuscript, item, todoMark(v.runId, one, mark, was?.reason ?? '', at))
      return was?.marked_at === before?.markedAt ? withMark(file, todo.manuscript, item, replaced) : null
    })
    if (mark && isFiled) filed = { markedAt: at, replaced }
  }
  await update($, answers, all => {
    const { [key]: _, ...rest } = all
    return choice ? { ...rest, [key]: { choice, isSent, ...filed } } : rest
  })
  if (v.todo) await refresh($)
}

async function notify($: $, text: string): Promise<void> {
  const sent = await $.ui.notify(text, { title: TITLE }).catch(() => null)
  if (!sent?.isSent) $.ui.toast(text, { timeoutMs: 10_000 })
}

// What changed since the last view: a toast per finished stage, a notification when the run ends or waits.
async function announce($: $, before: ManuscriptRunView | null, after: ManuscriptRunView): Promise<void> {
  if (!before || before.runId !== after.runId) return
  for (const stage of after.stages) {
    const was = before.stages.find(one => one.id === stage.id)
    if (!was || FINISHED.includes(was.state) || !FINISHED.includes(stage.state)) continue
    const said = stage.state === 'done' ? 'finished' : stage.state
    const detail = counts(stage)
    $.ui.toast(`${stage.label} ${said}${detail ? `: ${detail}` : ''}`)
  }
  if (!before.waitingFor && after.waitingFor) {
    await notify($, `${after.label} waits for your answer: ${after.waitingFor.questions.join(' · ')}`)
  } else if (!before.isWaiting && after.isWaiting) {
    await notify($, `${after.label}: ${after.decisions.length} decisions wait for you`)
  } else if (!before.isFinished && after.isFinished) {
    await notify($, `${after.label}: the run finished`)
  }
}

async function refresh($: $, isForced = false): Promise<void> {
  if (refreshing) return refreshing
  refreshing = (async () => {
    const run = runPath
    if (!run) return
    const stat = await $.fs.stat(join(run, 'run.json')).catch(() => null)
    if (!stat) {
      await update($, problem, () => `No run.json in ${run}.`)
      return
    }
    const stamp = stampOf(stat)
    if (stamp !== runStamp || isForced || !data) {
      const json = (await readJson($, join(run, 'run.json'))) as RunJson | null
      // runs.py replaces run.json in one rename, so a read that fails is retried at the next tick
      if (!json?.skills) return
      runStamp = stamp
      data = json
      findings = await readFindings($, run, json)
      await readReferees($, run, json)
      await readTitle($, run, json)
    }
    await readFiles($, run)
    await readMarks($, marksFile(data, findings))
    const next = buildView({ runPath: run, data, findings, files, referees, title, marks, now: await $.clock.now() })
    const before = await read($, view)
    await update($, view, () => next)
    await update($, problem, () => null)
    $.ui.status(statusLine(next, tally(next, await read($, answers)).open))
    await announce($, before, next)
  })().finally(() => {
    refreshing = null
  })

  return refreshing
}

async function openFile($: $, path: string): Promise<void> {
  if (!opener) {
    if ((await $.env.get('OS')) === 'Windows_NT') opener = ['cmd', '/c', 'start', '']
    else {
      const uname = await $.process.run(['uname', '-s']).catch(() => null)
      opener = uname?.stdout.trim() === 'Darwin' ? ['open'] : ['xdg-open']
    }
  }
  const ran = await $.process.run([...opener, path], { timeoutMs: 15_000 }).catch(() => null)
  if (!ran || ran.exitCode !== 0) $.ui.toast(`Could not open ${path}`)
}

// /manuscript-status and the show_run tool: watch the run a path names (or the one already watched, or this
// folder's project's newest), open the pane and answer with the run's state in text.
async function show($: $, given: string): Promise<string> {
  const arg = given.trim()
  if (arg === 'forget') {
    runPath = null
    data = null
    await $.store.delete('runPath')
    await update($, view, () => null)
    await update($, problem, () => 'No run chosen. /manuscript-status PATH shows one.')
    $.ui.status(undefined)
    return 'Stopped watching the manuscript run.'
  }
  const found = arg ? await locate($, arg) : (runPath ?? (await locate($, await $.session.root())))
  if (!found) {
    const where = arg || 'this folder or its parents'
    return `No manuscript run found in ${where}. Give a run folder or a project folder (one with ${PROJECT_FILE}).`
  }
  await choose($, found)
  await refresh($, true)
  await $.ui.open({ id: PANE, title: TITLE })
  const v = await read($, view)

  return v ? summary(v) : ((await read($, problem)) ?? `Could not read ${found}/run.json.`)
}

function summary(v: ManuscriptRunView): string {
  const lines = [statusLine(v), ...(v.title ? [`Manuscript: ${v.title}`] : []), `Run: ${v.runPath}`]
  for (const phase of v.phases) {
    const own = v.stages.filter(stage => stage.phase === phase.id)
    const parts = own.map(stage => `${stage.label} ${stage.state}${counts(stage) ? ` (${counts(stage)})` : ''}`)
    lines.push(`${phase.label} ${phase.done}/${phase.total}: ${parts.join('; ')}`)
  }
  if (v.waitingFor) lines.push('The run waits for your answer:', ...v.waitingFor.questions.map(question => `- ${question}`))
  const marked = v.decisions.filter(one => one.mark).length
  if (v.decisions.length) {
    const where = marked && v.todo ? `, ${marked} of them marked in ${v.todo.path}` : ''
    lines.push(`${v.decisions.length} decisions for the authors${where}.`)
  }
  if (v.dashboard) lines.push(`Dashboard: ${v.dashboard}`)

  return lines.join('\n')
}

const ICON: Record<ManuscriptStage['state'], string> = {
  done: '✓',
  reused: '↺',
  partial: '◐',
  blocked: '✕',
  skipped: '–',
  running: '●',
  next: '›',
  pending: '○',
}
const COLOR: Record<ManuscriptStage['state'], string> = {
  done: 'success',
  reused: 'success',
  partial: 'warning',
  blocked: 'error',
  skipped: 'inactive',
  running: 'warning',
  next: 'suggestion',
  pending: 'inactive',
}

const bar = (done: number, total: number, width: number) => {
  const filled = total === 0 ? 0 : Math.round((done / total) * width)
  return `${'█'.repeat(filled)}${'░'.repeat(width - filled)}`
}
const clip = (text: string, width: number) => (text.length <= width ? text : `${text.slice(0, Math.max(0, width - 1))}…`)
const cut = (text: string, width: number) => clip(text, width).padEnd(width)

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// The run's decisions with neither an answer here nor a mark in STEM.todo.json, and the answers given but not yet
// sent to Claude.
function tally(v: ManuscriptRunView, given: Record<string, ManuscriptAnswer>) {
  const keys = decisionKeys(v.runId, v.decisions)
  return {
    keys,
    open: keys.filter((key, n) => !given[key] && !v.decisions[n]!.mark).length,
    unsent: keys.filter(key => given[key] && !given[key]!.isSent).length,
  }
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
// "2026-10-28T09:15:00.000Z" reads "28 Oct 2026", as the To-do tab writes dates
const day = (iso: string) => {
  const found = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  return found ? `${Number(found[3])} ${MONTHS[Number(found[2]) - 1]} ${found[1]}` : ''
}

// The Decisions pane, titled with the manuscript so a session watching another paper's run says which.
async function openDecisions($: $, v: ManuscriptRunView): Promise<void> {
  await $.ui.open({ id: DECISIONS, title: `Decisions: ${v.label}`, focus: true })
}

// One message with every answer not sent yet, as the person's own: it runs once the session is idle. Marked sent
// at once, so a second press cannot send them twice; put back if the prompt does not enter.
async function sendAnswers($: $, v: ManuscriptRunView): Promise<void> {
  const given = await read($, answers)
  const text = answersMessage(v, given)
  const keys = new Set(decisionKeys(v.runId, v.decisions).filter(key => given[key] && !given[key]!.isSent))
  if (keys.size === 0) return
  const mark = (isSent: boolean) =>
    update($, answers, all => Object.fromEntries(Object.entries(all).map(([key, one]) => [key, keys.has(key) ? { ...one, isSent } : one])))
  await mark(true)
  void $.prompt.submit({ text, asUser: true }).then(
    async result => {
      if (result.drop === undefined) return
      await mark(false)
      $.ui.toast(`The answers were not sent: ${result.drop}`)
    },
    async () => {
      await mark(false)
      $.ui.toast('The answers could not be sent; they are kept in the Decisions pane.')
    },
  )
}

// "Ask me in a new session": Claude is asked, in the person's words, to start a session of its own for the decision
// (the desktop app's sessions; elsewhere Claude asks here). Marked at once; put back if the prompt does not enter.
async function askInSession($: $, v: ManuscriptRunView, one: ManuscriptDecision, key: string): Promise<void> {
  const mark = (isAsked: boolean) => setAnswer($, v, one, key, isAsked ? 'session' : null, true)
  await mark(true)
  void $.prompt.submit({ text: sessionRequest(v, one), asUser: true }).then(
    async result => {
      if (result.drop === undefined) return
      await mark(false)
      $.ui.toast(`The new session was not asked for: ${result.drop}`)
    },
    async () => {
      await mark(false)
      $.ui.toast('The new session could not be asked for; the decision is kept in the Decisions pane.')
    },
  )
}

// "Write answer": the decision, named, in the prompt box, after whatever the person had typed.
async function writeAnswer($: $, draft: string): Promise<boolean> {
  const box = await $.prompt.read()
  const filled = await $.prompt
    .fill({ text: box.text.trim() ? `\n${draft}` : draft, mode: box.text.trim() ? 'append' : 'replace' })
    .catch(() => null)
  if (!filled?.isFilled) $.ui.toast('The prompt box could not take the answer; type it there yourself.')

  return Boolean(filled?.isFilled)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({
      name: 'manuscript-status',
      description: 'Show a manuscript-skills run in the Manuscript run pane (newest run, or a path you give)',
      argumentHint: '[run folder | project folder | forget]',
      immediate: true,
    })
    await $.tool.register({
      name: 'show_run',
      description:
        "Show a manuscript-skills run's progress to the person in the Manuscript run pane and answer with its state: " +
        'stages, counts, decisions. Give the run folder, or a manuscript project folder for its newest run.',
      inputSchema: {
        type: 'object',
        properties: { path: { type: 'string', description: 'A run folder, its run.json, or a project folder' } },
        required: ['path'],
      },
    })
    // This folder's project only: the run it last watched, else its newest. The status line shows it; the pane
    // opens when this session works on a run (runs.py) or the person asks, never for a run of another folder.
    const local = await locate($, e.cwd)
    const kept = (await $.store.get('runPath')) as string | undefined
    const found = local && kept && parent(kept) === parent(local) && (await $.fs.exists(join(kept, 'run.json'))) ? kept : local
    if (found) {
      await choose($, found)
      await refresh($, true)
    }
    $.clock.every(REFRESH_MS, () => void refresh($))

    return started
  })

  on('command.run', { command: 'manuscript-status' }, async ($, e) => ({ text: await show($, e.args) })).catch(() => ({
    text: 'The manuscript run could not be read; the run itself is unaffected.',
  }))

  // The same for the model: a coordinator that starts a run, or a person who names one in the chat.
  on('tool.call', { tool: 'mcp__manuscript-skills__show_run' }, async ($, e) => {
    const text = await show($, String((e as { path?: unknown }).path ?? ''))

    return { result: text, text }
  }).catch(() => {
    const text = 'The manuscript run could not be read; the run itself is unaffected.'
    return { result: text, text }
  })

  // A runs.py call changed run.json: find the run it names (or `start` printed), refresh now, and open the pane
  // the first time this session works on that run. The command has run; this only delays its result by the reads.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    if (/\bruns\.py\b/.test(e.command)) {
      const said = `${e.command}\n${ran.text ?? ''}`
      const token = said.split(/[\s'"=]+/).find(word => /^([\\/]|[A-Za-z]:|~)/.test(word) && RUN_ID.test(word))
      const found = token ? await locate($, token) : null
      if (found) await choose($, found)
      await refresh($, true)
      if (found && found !== offered) {
        offered = found
        await $.ui.open({ id: PANE, title: TITLE })
      }
    }

    return ran
  }).catch(($, e, next) => next(e))

  // The band names the manuscript, counts what still waits and opens the Decisions pane, where the answers are.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const v = await read($, view)
    if (e.props.hasSurvey || !v?.isWaiting) return next(e)
    const asked = v.waitingFor?.questions ?? []
    const { open, unsent } = tally(v, await read($, answers))
    if (!v.waitingFor && open === 0 && unsent === 0) return next(e)
    const signature = `${v.runId}:${asked.join('|')}:${open}:${unsent}`
    if ((await read($, hiddenBand)) === signature) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    const waits = open > 0 ? `${plural(open, 'decision')} wait${open === 1 ? 's' : ''} for you` : ''
    const held = unsent > 0 ? `${plural(unsent, 'answer')} not sent yet` : ''

    return (
      <Box flexDirection="row" gap={1}>
        <Text color="warning">
          {v.waitingFor
            ? `${v.label} waits for your answer: ${asked[0] ?? ''}${asked.length > 1 ? ` (+${asked.length - 1} more)` : ''}`
            : `${v.label}: ${[waits, held].filter(Boolean).join(' · ')}`}
        </Text>
        <Button
          key="open-decisions"
          label={v.waitingFor ? 'Open questions' : 'Open decisions'}
          variant="primary"
          onPress={() => openDecisions($, v)}
        />
        <Button key="hide-band" label="Hide" onPress={() => update($, hiddenBand, () => signature)} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const v = await read($, view)
    if (!v) {
      const why = (await read($, problem)) ?? 'No manuscript run found yet.'
      return (
        <Box flexDirection="column">
          <Text dimColor>{why}</Text>
          <Text dimColor>/manuscript-status PATH shows a run folder or a project's newest run.</Text>
        </Box>
      )
    }
    const width = Math.max(30, e.props.bodyColumns)
    const now = Date.now()
    const isEnd = v.isWaiting && !v.waitingFor
    const open = (path: string) => () => void openFile($, path)

    const header = (
      <Box flexDirection="column" marginBottom={1}>
        <Text bold>{v.label}</Text>
        {v.title && <Text wrap="wrap">{v.title}</Text>}
        <Text dimColor wrap="truncate-end">
          {v.startedAt ? `started ${duration(now - v.startedAt)} ago` : ''}
          {v.lastRecordAt ? ` · last record ${duration(now - v.lastRecordAt)} ago` : ''} · {v.runId}
        </Text>
        <Text color={v.isWaiting ? 'warning' : v.isFinished ? 'success' : 'text'}>
          {v.waitingFor
            ? `Waiting for your answer${v.waitingFor.since ? ` for ${duration(now - v.waitingFor.since)}` : ''}`
            : v.isWaiting
            ? `Waiting for you: ${v.decisions.length} decisions`
            : v.isFinished
              ? 'Finished'
              : v.current
                ? `Now: ${v.current}`
                : 'Running'}
        </Text>
      </Box>
    )

    const barWidth = Math.min(24, Math.max(8, width - 26))
    const phases = v.phases.map(phase => (
      <Box key={`phase-${phase.id}`} flexDirection="column" marginBottom={1}>
        <Box flexDirection="row" gap={1}>
          <Text bold>{cut(phase.label, 9)}</Text>
          <Text color={phase.done === phase.total ? 'success' : 'warning'}>{bar(phase.done, phase.total, barWidth)}</Text>
          <Text dimColor>
            {phase.done}/{phase.total}
          </Text>
        </Box>
        {v.stages
          .filter(stage => stage.phase === phase.id)
          .map(stage => {
            const detail = counts(stage)
            const time = duration(stage.elapsedMs, stage.isElapsedApprox)
            return (
              <Box key={`stage-${stage.id}`} flexDirection="column">
                <Box flexDirection="row" gap={1}>
                  <Text color={COLOR[stage.state]}>{ICON[stage.state]}</Text>
                  <Text dimColor={stage.state === 'pending'} wrap="truncate-end">
                    {cut(stage.label, 19)}
                  </Text>
                  <Text dimColor>{time.padStart(7)}</Text>
                  {stage.state === 'running' && <Text color="warning">running</Text>}
                  {stage.state === 'next' && <Text color="suggestion">next</Text>}
                  {stage.report && (
                    <Button key={`report-${stage.id}`} label="report" plain onPress={open(stage.report)} />
                  )}
                </Box>
                {detail && (
                  <Box paddingLeft={2}>
                    <Text dimColor wrap="truncate-end">
                      {detail}
                    </Text>
                  </Box>
                )}
              </Box>
            )
          })}
      </Box>
    ))

    const questions = v.waitingFor && (
      <Box key="questions" flexDirection="column" marginBottom={1}>
        <Text bold color="warning">
          The run waits for your answer
        </Text>
        {v.waitingFor.questions.map(question => (
          <Text wrap="wrap">· {question}</Text>
        ))}
      </Box>
    )

    // The decisions themselves are read and answered in their own pane; here, how many and the way there.
    const { open: unanswered, unsent } = tally(v, await read($, answers))
    const decisions = v.decisions.length > 0 && (
      <Box key="decisions" flexDirection="row" flexWrap="wrap" columnGap={1} marginBottom={1}>
        <Text bold color={isEnd && unanswered > 0 ? 'warning' : 'text'}>
          {isEnd ? 'Decisions for you' : 'Held for the authors'}: {unanswered} of {v.decisions.length} open
          {unsent > 0 ? ` · ${plural(unsent, 'answer')} not sent` : ''}
        </Text>
        <Button key="open-decisions" label="Open decisions" onPress={() => openDecisions($, v)} />
      </Box>
    )

    const grid = v.referees && (
      <Box key="referees" flexDirection="column" marginBottom={1}>
        <Text bold>Referees</Text>
        {(() => {
          const seatWidth = 17
          const cell = Math.max(8, Math.floor((width - seatWidth) / Math.max(1, v.referees.venues.length)) - 1)
          return [
            <Box key="venues" flexDirection="row" gap={1}>
              <Text dimColor>{cut('', seatWidth - 1)}</Text>
              {v.referees.venues.map(venue => (
                <Text dimColor>
                  {cut(venue, cell)}
                </Text>
              ))}
            </Box>,
            ...v.referees.seats.map(seat => (
              <Box key={`seat-${seat.seat}`} flexDirection="row" gap={1}>
                <Text>{cut(seat.seat, seatWidth - 1)}</Text>
                {seat.cells.map((said, n) => (
                  <Text
                    color={said === 'accept' ? 'success' : said === 'minor' ? 'success' : said === 'reject' ? 'error' : 'warning'}
                  >
                    {cut(said ?? '–', cell)}
                  </Text>
                ))}
              </Box>
            )),
          ]
        })()}
      </Box>
    )

    const settings = (
      <Box key="settings" flexDirection="column" marginBottom={1}>
        <Text bold>Settings</Text>
        {v.settings.map(setting => (
          <Text wrap="wrap">
            {setting.key}: <Text bold>{setting.value}</Text>
            <Text dimColor>
              {setting.source ? ` (${setting.source})` : ''}
              {setting.meaning ? ` · ${setting.meaning}` : ''}
            </Text>
          </Text>
        ))}
      </Box>
    )

    const outputs = (
      <Box key="outputs" flexDirection="column">
        <Text bold>Open</Text>
        <Box flexDirection="row" flexWrap="wrap" columnGap={1}>
          {v.outputs.map(output => (
            <Button key={`open-${output.key}`} label={output.label} onPress={open(output.path)} />
          ))}
        </Box>
      </Box>
    )

    return (
      <Box flexDirection="column">
        {header}
        {questions}
        {decisions}
        {phases}
        {grid}
        {settings}
        {outputs}
      </Box>
    )
  })

  // The decisions the run left for the authors, each a row pressed to unfold it: its whole summary and, unfolded,
  // what the finding says beyond it and the answers: a new session that asks the authors about it, go ahead,
  // leave as is, or write an answer in the prompt box. Go ahead and leave go to Claude together in one message,
  // from the button at the top, and are marked in STEM.todo.json at once, where a row shows the mark the To-do
  // tab made too.
  on('ui.render', { component: 'Pane', requestId: DECISIONS }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const v = await read($, view)
    if (!v) {
      return (
        <Box flexDirection="column">
          <Text dimColor>{(await read($, problem)) ?? 'No manuscript run found yet.'}</Text>
          <Text dimColor>/manuscript-status PATH shows a run folder or a project's newest run.</Text>
        </Box>
      )
    }
    const given = await read($, answers)
    const { keys, open, unsent } = tally(v, given)
    const unfolded = new Set(await read($, unfoldedDecisions))
    const unfold = (key: string) => () =>
      update($, unfoldedDecisions, list =>
        list.includes(key) ? list.filter(one => one !== key) : [...list.filter(one => one.startsWith(`${v.runId}:`)), key],
      )
    const answer = (key: string, one: ManuscriptDecision, choice: ManuscriptAnswer['choice'] | null) => () =>
      setAnswer($, v, one, key, choice)
    const SAID: Record<ManuscriptAnswer['choice'], [string, string]> = {
      'go-ahead': ['go ahead', 'success'],
      leave: ['leave as is', 'inactive'],
      written: ['answered in the chat', 'success'],
      session: ['asked in a new session', 'success'],
    }
    const MARKED: Record<ManuscriptTodoMark['mark'], string> = { approved: 'success', redundant: 'inactive' }

    const header = (
      <Box key="header" flexDirection="column" marginBottom={1}>
        <Text bold>{v.label}</Text>
        {v.title && <Text wrap="wrap">{v.title}</Text>}
        <Text color={open > 0 ? 'warning' : 'success'}>
          {open > 0 ? `${open} of ${plural(v.decisions.length, 'decision')} wait for you` : `All ${plural(v.decisions.length, 'decision')} answered`}
        </Text>
        <Text dimColor wrap="wrap">
          Press a decision to open it: have a new session ask you about it, go ahead as it suggests, leave the text
          as it is, or write your own answer in the prompt box. Send the go-aheads and leaves to Claude together.
        </Text>
        {v.todo && (
          <Text dimColor wrap="wrap">
            {`Go ahead and leave as is also mark a decision approved or redundant in ${fileName(v.todo.path)} beside the manuscript, the file the dashboard's To-do tab saves and the next run reads; its marks count as answers here.`}
          </Text>
        )}
        {unsent > 0 && (
          <Box marginTop={1}>
            <Button
              key="send-answers"
              variant="primary"
              label={`Send ${plural(unsent, 'answer')} to Claude`}
              onPress={() => sendAnswers($, v)}
            />
          </Box>
        )}
      </Box>
    )

    const questions = v.waitingFor && (
      <Box key="questions" flexDirection="column" marginBottom={1}>
        <Text bold color="warning">
          The run waits for your answer
        </Text>
        {v.waitingFor.questions.map((question, n) => (
          <Box key={`question-${n}`} flexDirection="column">
            <Text wrap="wrap">· {question}</Text>
            <Box paddingLeft={2}>
              <Button
                key={`answer-question-${n}`}
                label="Write answer"
                onPress={() =>
                  void writeAnswer($, `On the question the ${v.label} manuscript run waits for (${v.runPath}), "${question}": `)
                }
              />
            </Box>
          </Box>
        ))}
      </Box>
    )

    const rows = v.decisions.map((one, n) => {
      const key = keys[n]!
      const isOpen = unfolded.has(key)
      const mine = given[key]
      const said = mine && SAID[mine.choice]
      // the file's mark, unless it is the one this answer made
      const filed = one.mark && one.mark.markedAt !== mine?.markedAt ? one.mark : null
      const reason = one.mark?.reason ? `: “${one.mark.reason}”` : ''
      const where = [one.stage, one.section].filter(Boolean).join(' · ')
      return (
        <Box key={`row-${key}`} flexDirection="column" marginBottom={isOpen ? 1 : 0}>
          <Button key={`decision-${key}`} plain dimColor={Boolean(mine?.isSent || (!mine && filed))} onPress={unfold(key)}>
            <Text dimColor>{`${isOpen ? '▾' : '▸'} ${one.id}`}</Text> {one.summary}
            {said && (
              <Text color={said[1]}>
                {` · ${said[0]}${mine!.isSent && (mine!.choice === 'go-ahead' || mine!.choice === 'leave') ? ', sent' : ''}`}
                {filed ? '' : reason}
              </Text>
            )}
            {filed && <Text color={MARKED[filed.mark]}>{` · marked ${filed.mark}${reason}`}</Text>}
          </Button>
          {isOpen && (
            <Box flexDirection="column" paddingLeft={2}>
              {where && (
                <Text dimColor wrap="wrap">
                  {where}
                </Text>
              )}
              {one.detail && <Text wrap="wrap">{one.detail}</Text>}
              {one.action && <Text wrap="wrap">→ {one.action}</Text>}
              {one.mark && v.todo && (
                <Text dimColor wrap="wrap">
                  {`Marked ${one.mark.mark}${one.mark.markedAt ? ` on ${day(one.mark.markedAt)}` : ''} in ${fileName(v.todo.path)}${reason}`}
                </Text>
              )}
              <Box flexDirection="row" flexWrap="wrap" columnGap={1} marginTop={1}>
                <Button
                  key={`session-${key}`}
                  variant="primary"
                  label="Ask me in a new session"
                  onPress={() => askInSession($, v, one, key)}
                />
                {one.action && <Button key={`go-ahead-${key}`} label="Go ahead" onPress={answer(key, one, 'go-ahead')} />}
                <Button key={`leave-${key}`} label="Leave as is" onPress={answer(key, one, 'leave')} />
                <Button
                  key={`write-${key}`}
                  label="Write answer"
                  onPress={async () => {
                    if (await writeAnswer($, answerDraft(v, one))) await answer(key, one, 'written')()
                  }}
                />
                {mine && (!mine.isSent || mine.choice === 'written' || mine.choice === 'session') && (
                  <Button key={`undo-${key}`} label="Undo" onPress={answer(key, one, null)} />
                )}
              </Box>
            </Box>
          )}
        </Box>
      )
    })

    return (
      <Box flexDirection="column">
        {header}
        {questions}
        {v.decisions.length > 0 ? rows : <Text dimColor>The run holds no decisions for the authors.</Text>}
      </Box>
    )
  })
}
