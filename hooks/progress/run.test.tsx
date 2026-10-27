import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { buildView, statusLine } from './model'
import type { RunJson } from './model'

const PROJECT = '/work/paper/v0.6'
const RUN = `${PROJECT}/reviews/20261027T125139Z-488af17b`
const at = (minute: number) => `2026-10-27T13:${String(minute).padStart(2, '0')}:00+00:00`
const change = (skill: string, n: number, minute: number) => ({
  section: `Section ${n}`,
  path: `${skill}/changes/${String(n).padStart(4, '0')}.md`,
  recorded_at: at(minute),
})
const empty = { artifacts: [], issues: [], changes: [], commands: [] }

// A run shaped like the live Paper 1 v0.6 run: review done, revise done, the prose edit running.
function runJson(prose = 'running', improve = 'running'): RunJson {
  return {
    run_id: '20261027T125139Z-488af17b',
    started_at: '2026-10-27T12:51:39+00:00',
    context: {
      effective: { reports: 'file', edits: 'apply', versions: 'in-place', keep: 'everything', peer_review: 'auto' },
      sources: { reports: 'project', edits: 'project', versions: 'default', keep: 'default', peer_review: 'default' },
      project_root: PROJECT,
    },
    inputs: [{ original: `${PROJECT}/paper1-just-dna-lite.md`, snapshot: 'inputs/01-paper1-just-dna-lite.md' }],
    skills: {
      'manuscript-improve': {
        ...empty,
        status: improve,
        artifacts: [
          { path: 'manuscript-improve/stage-brief-revise.md', role: 'other', recorded_at: at(10) },
          { path: 'manuscript-improve/revise/report.md', role: 'other', recorded_at: at(30) },
        ],
        changes: [change('manuscript-improve', 1, 20), change('manuscript-improve', 2, 21)],
      },
      'manuscript-integrity-check': {
        ...empty,
        status: 'completed',
        artifacts: [
          { path: 'manuscript-integrity-check/commands/0001.stdout.txt', role: 'check', recorded_at: at(1) },
          { path: 'manuscript-integrity-check/report.md', role: 'report', recorded_at: at(5) },
        ],
      },
      'manuscript-peer-review': {
        ...empty,
        status: 'completed',
        artifacts: [
          { path: 'manuscript-peer-review/findings.adjudicated.json', role: 'adjudication', sha256: 'a', recorded_at: at(6) },
          { path: 'manuscript-peer-review/report.md', role: 'report', recorded_at: at(9) },
        ],
      },
      'manuscript-prose-edit': {
        ...empty,
        status: prose,
        changes: [change('manuscript-prose-edit', 1, 40), change('manuscript-prose-edit', 2, 41)],
      },
    },
  }
}

const FINDINGS = {
  findings: [
    { id: 'IC-1', summary: 'A number does not add up', decision: false },
    { id: 'IC-2', summary: 'Which journal comes first', decision: true },
  ],
  changes: [{ id: 'IC-C1' }],
}
const ADJUDICATED = {
  reports: [
    { seat: 'skeptic', recommendations: [{ venue: 'iscience', recommendation: 'major-revision' }] },
    { seat: 'champion', recommendations: [{ venue: 'iscience', recommendation: 'minor-revision' }] },
  ],
}

test('the status line reads like the run', () => {
  const view = buildView({
    runPath: RUN,
    data: runJson(),
    findings: { 'manuscript-integrity-check': { findings: 2, proposals: 1, decisions: [{ id: 'IC-2', summary: 'x' }] } },
    files: { dashboard: null, word: null, workbook: null, corrected: null, recheck: null, questions: [] },
    referees: null,
    now: Date.parse(at(50)),
  })

  expect(statusLine(view)).toBe('Paper 1 v0.6 · 3 of 13 stages · prose edit running · 4 edits applied · 1 held')
  expect(view.phases.map(phase => `${phase.label} ${phase.done}/${phase.total}`)).toEqual([
    'Review 2/2',
    'Editing 1/5',
    'Assembly 0/6',
  ])
  expect(view.stages.find(stage => stage.id === 'revise')?.edits).toBe(2)
  expect(view.isWaiting).toBe(false)
})

// The run folder as the mod's `$.fs` calls see it; `version` moves run.json's modification time.
function folder(on: On, files: Map<string, string>, version: { n: number }) {
  const isDir = (path: string) => [...files.keys()].some(one => one.startsWith(`${path}/`))
  on('fs.exists', (_, e) => ({ value: files.has(e.path) || isDir(e.path) }))
  on('fs.read', (_, e) => {
    const text = files.get(e.path)
    if (text === undefined) throw new Error(`ENOENT ${e.path}`)
    return { value: text }
  })
  on('fs.stat', (_, e) => {
    const text = files.get(e.path)
    if (text === undefined) throw new Error(`ENOENT ${e.path}`)
    return { value: { kind: 'file' as const, size: text.length, mtimeMs: version.n, isLink: false } }
  })
  on('fs.list', (_, e) => {
    const names = new Map<string, 'file' | 'dir'>()
    for (const path of files.keys()) {
      if (!path.startsWith(`${e.path}/`)) continue
      const [head, ...rest] = path.slice(e.path.length + 1).split('/')
      names.set(head!, rest.length ? 'dir' : 'file')
    }
    return { value: [...names].map(([name, kind]) => ({ name, kind, size: 1, mtimeMs: version.n, isLink: false })) }
  })
}

// The command as the person types it in a fullscreen terminal or the desktop app.
const TYPED = {
  command: 'manuscript-status',
  origin: { kind: 'composer' },
  presentation: { isFullscreen: true, columns: 160 },
} as const

const PANE = {
  plugin: 'manuscript-skills',
  component: 'Pane',
  requestId: 'manuscript-run',
  props: {
    title: 'Manuscript run',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 80 },
    view: {},
  },
} as const

test('the pane shows the live run on the terminal and the desktop, and a finished stage toasts', async ($, on) => {
  const version = { n: 1 }
  const files = new Map<string, string>([
    [`${PROJECT}/.manuscript-skills.yaml`, 'schema_version: 1\noutput_dir: reviews\n'],
    [`${RUN}/run.json`, JSON.stringify(runJson())],
    [`${RUN}/manuscript-integrity-check/findings.json`, JSON.stringify(FINDINGS)],
    [`${RUN}/manuscript-peer-review/findings.adjudicated.json`, JSON.stringify(ADJUDICATED)],
  ])
  const statuses: (string | undefined)[] = []
  const toasts: string[] = []
  folder(on, files, version)
  const clock = mock.clock(on, { now: Date.parse(at(50)) })
  mock.store(on)
  mock.env(on, { HOME: '/home/author' })
  on('command.register', () => ({ value: { command: 'manuscript-status' } }))
  on('tool.register', () => ({ value: { tool: 'mcp__manuscript-skills__show_run' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', (_, e) => (statuses.push(e.text), { value: undefined }))
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))

  await $.session.start({ cwd: PROJECT, surface: 'desktop', isInteractive: true })
  expect(statuses.at(-1)).toBe('Paper 1 v0.6 · 3 of 13 stages · prose edit running · 4 edits applied · 1 held')

  const answer = await $.command.run({ ...TYPED, args: RUN })
  expect(answer.text).toContain('Editing 1/5')
  // typed loosely: the session's connected MCP tools make the exact call type too deep for the compiler
  const callTool = $.tool.call as unknown as (e: { tool: string; path: string }) => Promise<{ text?: string }>
  const called = await callTool({ tool: 'mcp__manuscript-skills__show_run', path: `${RUN}/run.json` })
  expect(called.text).toContain('Review 2/2')

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.find({ type: 'Text', text: /Prose edit/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^running$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'report-manuscript-integrity-check' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /major/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /apply/ })).toBeDefined()
    await ui.unmount()
  }

  files.set(`${RUN}/run.json`, JSON.stringify(runJson('completed')))
  version.n = 2
  await clock.advance(15_000)
  expect(toasts).toContain('Prose edit finished: 2 edits')
})

test('the pane opens by itself only for the run this session works on', async ($, on) => {
  const OTHER = '/work/thesis/reviews/20261020T090000Z-0badc0de'
  const other = { ...runJson(), run_id: '20261020T090000Z-0badc0de', inputs: [{ original: '/work/thesis/thesis.md', snapshot: 'x' }] }
  const files = new Map<string, string>([
    [`${PROJECT}/.manuscript-skills.yaml`, 'schema_version: 1\n'],
    [`${RUN}/run.json`, JSON.stringify(runJson())],
    [`${OTHER}/run.json`, JSON.stringify(other)],
  ])
  const statuses: (string | undefined)[] = []
  const opened: string[] = []
  folder(on, files, { n: 1 })
  mock.clock(on, { now: Date.parse(at(50)) })
  // the last run watched, in another folder's project
  mock.store(on, { runPath: OTHER })
  mock.env(on, { HOME: '/home/author' })
  on('command.register', () => ({ value: { command: 'manuscript-status' } }))
  on('tool.register', () => ({ value: { tool: 'mcp__manuscript-skills__show_run' } }))
  on('ui.open', (_, e) => (opened.push(e.id), { value: { isPlaced: true } }))
  on('ui.status', (_, e) => (statuses.push(e.text), { value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', { tool: 'Bash' }, () => ({ result: { stdout: '', stderr: '', interrupted: false } }))

  await $.session.start({ cwd: PROJECT, surface: 'desktop', isInteractive: true })
  expect(statuses.at(-1)).toContain('Paper 1 v0.6 ·')
  expect(opened).toEqual([])

  const command = `uv run skills/manuscript-integrity-check/scripts/runs.py add ${RUN} --skill manuscript-prose-edit`
  await $.tool.call({ tool: 'Bash', command })
  expect(opened).toEqual(['manuscript-run'])
  // closed by the person, it stays closed for the rest of the run
  await $.tool.call({ tool: 'Bash', command })
  expect(opened).toEqual(['manuscript-run'])
})

test('a finished run with decisions raises the band, which opens them', async ($, on) => {
  const files = new Map<string, string>([
    [`${RUN}/run.json`, JSON.stringify(runJson('completed', 'completed'))],
    [`${RUN}/manuscript-integrity-check/findings.json`, JSON.stringify(FINDINGS)],
  ])
  const opened: { focus?: boolean }[] = []
  folder(on, files, { n: 1 })
  mock.clock(on, { now: Date.parse(at(59)) })
  mock.store(on)
  mock.env(on, { HOME: '/home/author' })
  on('ui.open', (_, e) => (opened.push(e), { value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))

  await $.command.run({ ...TYPED, args: RUN })
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({
      plugin: 'manuscript-skills',
      surface,
      component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 6, bodyColumns: 80, scroll: { offset: 0, bodyRows: 6 }, view: {} },
    })
    expect((await band.find({ type: 'Text', text: /decisions wait for you/ }))?.text).toBe('Paper 1 v0.6: 1 decisions wait for you')
    await band.press({ key: 'open-decisions' })
    await band.unmount()
  }
  expect(opened.at(-1)?.focus).toBe(true)
})

test('progress records give exact times, the coordinator stages, the plan and the counts', () => {
  const data = runJson('completed')
  // story and journal adaptation are not planned; the prose edit's findings file is packed, its counts kept
  data.plan = [
    'manuscript-integrity-check',
    'manuscript-peer-review',
    'revise',
    'manuscript-prose-edit',
    'manuscript-deslop',
    'manuscript-dashboard',
    'corrected',
    'recheck',
    'handover',
  ]
  data.skills['manuscript-improve']!.stages = {
    revise: { status: 'completed', started_at: at(10), finished_at: at(25), reason: '' },
    corrected: { status: 'running', started_at: at(45), finished_at: null, reason: '' },
  }
  data.skills['manuscript-prose-edit'] = {
    ...data.skills['manuscript-prose-edit']!,
    started_at: at(30),
    finished_at: at(42),
    counts: { findings: 5, proposals: 1, decisions: 3 },
  }
  const view = buildView({
    runPath: RUN,
    data,
    findings: {},
    files: { dashboard: null, word: null, workbook: null, corrected: null, recheck: null, questions: [] },
    referees: null,
    now: Date.parse(at(50)),
  })
  const stage = (id: string) => view.stages.find(one => one.id === id)

  expect(view.isPlanned).toBe(true)
  expect(view.stages.map(one => one.id)).toEqual([
    'manuscript-integrity-check',
    'manuscript-peer-review',
    'revise',
    'manuscript-prose-edit',
    'manuscript-deslop',
    'manuscript-dashboard',
    'corrected',
    'recheck',
    'word',
    'workbook',
    'handover',
  ])
  expect(stage('revise')).toMatchObject({ state: 'done', elapsedMs: 15 * 60_000, isElapsedApprox: false, edits: 2 })
  expect(stage('manuscript-prose-edit')).toMatchObject({
    state: 'done',
    elapsedMs: 12 * 60_000,
    isElapsedApprox: false,
    findings: 5,
    proposals: 1,
    held: 3,
  })
  expect(stage('corrected')).toMatchObject({ state: 'running', elapsedMs: 5 * 60_000, isElapsedApprox: false })
  expect(statusLine(view)).toBe('Paper 1 v0.6 · 4 of 11 stages · corrected version running · 4 edits applied · 3 held')
})

test('a run that stops for an answer says so, apart from the decisions held for the end', async ($, on) => {
  const stopped = { ...runJson(), waiting: { since: at(45), questions: ['Which journal should the paper go to first?'] } }
  const files = new Map<string, string>([
    [`${RUN}/run.json`, JSON.stringify(runJson())],
    [`${RUN}/manuscript-integrity-check/findings.json`, JSON.stringify(FINDINGS)],
    [`${RUN}/manuscript-peer-review/findings.adjudicated.json`, JSON.stringify(ADJUDICATED)],
  ])
  const version = { n: 1 }
  const notices: string[] = []
  const statuses: (string | undefined)[] = []
  folder(on, files, version)
  mock.clock(on, { now: Date.parse(at(50)) })
  mock.store(on)
  mock.env(on, { HOME: '/home/author' })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', (_, e) => (statuses.push(e.text), { value: undefined }))
  on('ui.toast', (_, e) => (notices.push(e.text), { value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))

  await $.command.run({ ...TYPED, args: RUN })
  files.set(`${RUN}/run.json`, JSON.stringify(stopped))
  version.n = 2
  // what the 15-second refresh would read; the command reads it at once
  await $.command.run({ ...TYPED, args: RUN })

  expect(statuses.at(-1)).toBe(
    'Paper 1 v0.6 · 3 of 13 stages · waits for your answer (1 question) · 4 edits applied · 1 held',
  )
  expect(notices).toContain('Paper 1 v0.6 waits for your answer: Which journal should the paper go to first?')
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({
      plugin: 'manuscript-skills',
      surface,
      component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: true, maxRows: 6, bodyColumns: 80, scroll: { offset: 0, bodyRows: 6 }, view: {} },
    })
    expect((await band.find({ type: 'Text', text: /waits for your answer/ }))?.text).toBe(
      'Paper 1 v0.6 waits for your answer: Which journal should the paper go to first?',
    )
    expect((await band.find({ type: 'Button', key: 'open-decisions' }))?.text).toBe('Open questions')
    await band.unmount()

    const pane = await $.ui.mount({ ...PANE, surface })
    expect(await pane.find({ type: 'Text', text: /The run waits for your answer/ })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: /Held for the authors \(1\)/ })).toBeDefined()
    await pane.unmount()
  }
})
