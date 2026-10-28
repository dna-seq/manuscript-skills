import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { buildView, manuscriptTitle, marksPath, runLabel, statusLine, summarizeFindings } from './model'
import type { MarksFile, RunJson } from './model'

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
          { path: 'manuscript-improve/revise/stage-report.md', role: 'other', recorded_at: at(30) },
        ],
        changes: [change('manuscript-improve', 1, 20), change('manuscript-improve', 2, 21)],
      },
      'manuscript-integrity-check': {
        ...empty,
        status: 'completed',
        artifacts: [
          { path: 'manuscript-integrity-check/commands/0001.stdout.txt', role: 'check', recorded_at: at(1) },
          { path: 'manuscript-integrity-check/stage-report.md', role: 'report', recorded_at: at(5) },
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
    findings: { 'manuscript-integrity-check': { findings: 2, proposals: 1, decisions: [{ id: 'IC-2', summary: 'x', findingIds: ['IC-2'] }] } },
    files: { dashboard: null, word: null, workbook: null, corrected: null, recheck: null, questions: [] },
    referees: null,
    now: Date.parse(at(50)),
  })

  expect(statusLine(view)).toBe('Paper 1 just-dna-lite v0.6 · 3 of 13 stages · prose edit running · 4 edits applied · 1 held')
  expect(view.phases.map(phase => `${phase.label} ${phase.done}/${phase.total}`)).toEqual([
    'Review 2/2',
    'Editing 1/5',
    'Assembly 0/6',
  ])
  expect(view.stages.find(stage => stage.id === 'revise')?.edits).toBe(2)
  expect(view.stages.find(stage => stage.id === 'revise')?.report).toBe(`${RUN}/manuscript-improve/revise/stage-report.md`)
  // Reports keep their names from before 0.33 in earlier runs: peer review's report.md opens all the same.
  expect(view.stages.find(stage => stage.id === 'manuscript-peer-review')?.report).toBe(`${RUN}/manuscript-peer-review/report.md`)
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
  on('fs.write', (_, e) => (files.set(e.path, e.text), { value: undefined }))
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
    title: 'Manuscript Skills · run',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 80 },
    view: {},
  },
} as const
const DECISIONS = { ...PANE, requestId: 'manuscript-decisions', props: { ...PANE.props, title: 'Manuscript Skills · decisions' } } as const
const BAND = {
  plugin: 'manuscript-skills',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 6, bodyColumns: 80, scroll: { offset: 0, bodyRows: 6 }, view: {} },
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
  mock.env(on, { HOME: '/home/user' })
  on('command.register', () => ({ value: { command: 'manuscript-status' } }))
  on('tool.register', () => ({ value: { tool: 'mcp__manuscript-skills__show_run' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', (_, e) => (statuses.push(e.text), { value: undefined }))
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))

  await $.session.start({ cwd: PROJECT, surface: 'desktop', isInteractive: true })
  expect(statuses.at(-1)).toBe('Paper 1 just-dna-lite v0.6 · 3 of 13 stages · prose edit running · 4 edits applied · 1 held')

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
  mock.env(on, { HOME: '/home/user' })
  on('command.register', () => ({ value: { command: 'manuscript-status' } }))
  on('tool.register', () => ({ value: { tool: 'mcp__manuscript-skills__show_run' } }))
  on('ui.open', (_, e) => (opened.push(e.id), { value: { isPlaced: true } }))
  on('ui.status', (_, e) => (statuses.push(e.text), { value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', { tool: 'Bash' }, () => ({ result: { stdout: '', stderr: '', interrupted: false } }))

  await $.session.start({ cwd: PROJECT, surface: 'desktop', isInteractive: true })
  expect(statuses.at(-1)).toContain('Paper 1 just-dna-lite v0.6 ·')
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
  const opened: { id: string; title?: string; focus?: boolean }[] = []
  folder(on, files, { n: 1 })
  mock.clock(on, { now: Date.parse(at(59)) })
  mock.store(on)
  mock.env(on, { HOME: '/home/user' })
  on('ui.open', (_, e) => (opened.push(e), { value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))

  await $.command.run({ ...TYPED, args: RUN })
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({ ...BAND, surface })
    expect((await band.find({ type: 'Text', text: /waits for you/ }))?.text).toBe('Paper 1 just-dna-lite v0.6: 1 decision waits for you')
    await band.press({ key: 'open-decisions' })
    await band.unmount()
    // the decisions open in a pane of their own, named for the manuscript, not in the progress pane
    expect(opened.at(-1)).toEqual({ id: 'manuscript-decisions', title: 'Manuscript Skills · decisions: Paper 1 just-dna-lite v0.6', focus: true })
  }

  // the progress pane counts them and opens the same pane
  const pane = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await pane.find({ type: 'Text', text: /Decisions for you/ }))?.text).toBe('Decisions for you: 1 of 1 open')
  await pane.press({ key: 'open-decisions' })
  expect(opened.at(-1)?.id).toBe('manuscript-decisions')
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
  expect(statusLine(view)).toBe('Paper 1 just-dna-lite v0.6 · 4 of 11 stages · corrected version running · 4 edits applied · 3 held')
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
  mock.env(on, { HOME: '/home/user' })
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
    'Paper 1 just-dna-lite v0.6 · 3 of 13 stages · waits for your answer (1 question) · 4 edits applied · 1 held',
  )
  expect(notices).toContain('Paper 1 just-dna-lite v0.6 waits for your answer: Which journal should the paper go to first?')
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({ ...BAND, surface, props: { ...BAND.props, isWorking: true } })
    expect((await band.find({ type: 'Text', text: /waits for your answer/ }))?.text).toBe(
      'Paper 1 just-dna-lite v0.6 waits for your answer: Which journal should the paper go to first?',
    )
    expect((await band.find({ type: 'Button', key: 'open-decisions' }))?.text).toBe('Open questions')
    await band.unmount()

    const pane = await $.ui.mount({ ...PANE, surface })
    expect(await pane.find({ type: 'Text', text: /The run waits for your answer/ })).toBeDefined()
    expect((await pane.find({ type: 'Text', text: /Held for the authors/ }))?.text).toBe('Held for the authors: 1 of 1 open')
    await pane.unmount()

    // the Decisions pane leads with the question, which the person answers in the prompt box
    const decisions = await $.ui.mount({ ...DECISIONS, surface })
    expect(await decisions.find({ type: 'Text', text: '· Which journal should the paper go to first?' })).toBeDefined()
    expect(await decisions.find({ type: 'Button', key: 'answer-question-0' })).toBeDefined()
    expect(await decisions.find({ type: 'Button', key: 'decision-20261027T125139Z-488af17b:Integrity check:IC-2' })).toBeDefined()
    await decisions.unmount()
  }
})


test('the label names the manuscript, and the title comes from its text', () => {
  const named = (original: string, root = '') =>
    runLabel({ run_id: 'r', started_at: at(0), skills: {}, inputs: [{ original, snapshot: 'x' }], context: { project_root: root } })
  // two papers of one person: each named apart, never "manuscript"
  const creator = '/home/user/just-module-creator/docs/manuscript'
  expect(named(`${creator}/manuscript.tex`, creator)).toBe('just-module-creator')
  const lite = '/home/user/just-dna-lite/docs/manuscript/v0.6'
  expect(named(`${lite}/paper1-just-dna-lite.md`, lite)).toBe('Paper 1 just-dna-lite v0.6')
  expect(named('/home/user/thesis/paper2.md')).toBe('thesis Paper 2')
  expect(named('/home/user/drafts/sirt6-aging.md')).toBe('sirt6-aging')
  // the paper's own name from its title wins; a title that opens with a sentence leaves the file's name
  const run = { run_id: 'r', started_at: at(0), skills: {}, inputs: [{ original: `${lite}/paper1-just-dna-lite.md`, snapshot: 'x' }], context: { project_root: lite } }
  expect(runLabel(run, 'Just-DNA-Lite: a Local-First Platform')).toBe('Just-DNA-Lite v0.6')
  expect(runLabel(run, 'Creating and Sharing Genomic Annotation Modules with AI: The Just-DNA Ecosystem')).toBe('Paper 1 just-dna-lite v0.6')

  const easrp = '\\easrpauthor{Anonymous}\n\\easrptitle{Creating and Sharing Genomic Annotation Modules with AI: The\nJust-DNA Ecosystem}\n\\maketitle'
  expect(manuscriptTitle(easrp, 'inputs/01-manuscript.tex')).toBe(
    'Creating and Sharing Genomic Annotation Modules with AI: The Just-DNA Ecosystem',
  )
  expect(manuscriptTitle('\\shorttitle{Short}\n\\title[Short]{A \\emph{real} title}', 'm.tex')).toBe('A real title')
  expect(manuscriptTitle('# **Just-DNA-Lite: a Local-First Platform**\n\n> Draft v0.6', 'inputs/01-paper1.md')).toBe(
    'Just-DNA-Lite: a Local-First Platform',
  )
  expect(manuscriptTitle('---\ntitle: "From the front matter"\n---\n# Introduction', 'paper.md')).toBe('From the front matter')
  expect(manuscriptTitle('No heading at all.', 'paper.md')).toBeNull()
})

test('the Decisions pane shows each decision whole and sends the answers to Claude in one message', async ($, on) => {
  // 22 decisions, as the just-module-creator run of 2026-10-26 holds, each summary wider than the pane
  const held = Array.from({ length: 22 }, (_, n) => ({
    id: `IC-${n + 1}`,
    summary: `Decision ${n + 1} about a claim whose wording only the authors can settle, longer than the pane is wide`,
    decision: true,
  }))
  const whole = {
    ...held[20]!,
    section: '4.2 Production catalog (Table 4)',
    detail: 'Four modules hold most of the catalog variants and are presented only as evidence the catalog works.',
    action: 'State what the registry records about these four modules.',
  }
  const files = new Map<string, string>([
    [`${RUN}/run.json`, JSON.stringify(runJson('completed', 'completed'))],
    [`${RUN}/inputs/01-paper1-just-dna-lite.md`, '# **Just-DNA-Lite: a Local-First Platform**\n\nText.'],
    [`${RUN}/manuscript-integrity-check/findings.json`, JSON.stringify({ findings: [...held.slice(0, 20), whole, held[21]] })],
  ])
  const submitted: { text: string; origin?: { kind: string; asUser?: true } }[] = []
  const filled: string[] = []
  folder(on, files, { n: 1 })
  mock.clock(on, { now: Date.parse(at(59)) })
  mock.store(on)
  mock.env(on, { HOME: '/home/user' })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))
  on('prompt.submit', (_, e) => (submitted.push(e), { text: e.text }))
  on('prompt.read', () => ({ value: { text: '', cursor: 0 } }))
  on('prompt.fill', (_, e) => (filled.push(e.text), { isFilled: true }))
  await $.command.run({ ...TYPED, args: RUN })

  const key = (id: string) => `20261027T125139Z-488af17b:Integrity check:${id}`
  const rows = async (ui: { findAll: (query: { type: string }) => Promise<{ key: string | undefined }[]> }) =>
    (await ui.findAll({ type: 'Button' })).filter(one => one.key?.startsWith('decision-'))
  for (const surface of ['terminal', 'desktop'] as const) {
    const pane = await $.ui.mount({ ...DECISIONS, surface })
    // named by the paper's own name from its title, not by its file or its kind
    expect(await pane.find({ type: 'Text', text: 'Just-DNA-Lite v0.6' })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: 'Just-DNA-Lite: a Local-First Platform' })).toBeDefined()
    expect((await pane.find({ type: 'Text', text: /wait for you$/ }))?.text).toBe('22 of 22 decisions wait for you')
    // every decision listed, its summary whole and wrapped, never cut
    expect(await rows(pane)).toHaveLength(22)
    // each row is one press, its summary whole
    expect((await pane.find({ type: 'Button', key: `decision-${key('IC-22')}` }))?.text).toContain(held[21]!.summary)
    expect(await pane.find({ type: 'Button', key: `go-ahead-${key('IC-21')}` })).toBeUndefined()
    await pane.unmount()
  }

  const pane = await $.ui.mount({ ...DECISIONS, surface: 'desktop' })
  // unfolded, a decision says where, why and what it suggests, with its answers
  await pane.press({ key: `decision-${key('IC-21')}` })
  expect(await pane.find({ type: 'Text', text: 'Integrity check · 4.2 Production catalog (Table 4)' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: whole.detail })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: `→ ${whole.action}` })).toBeDefined()
  expect(await pane.find({ type: 'Button', key: `session-${key('IC-21')}` })).toBeDefined()
  await pane.press({ key: `go-ahead-${key('IC-21')}` })
  // one with nothing suggested can be left or answered, not gone ahead with
  await pane.press({ key: `decision-${key('IC-1')}` })
  expect(await pane.find({ type: 'Button', key: `go-ahead-${key('IC-1')}` })).toBeUndefined()
  await pane.press({ key: `leave-${key('IC-1')}` })
  expect((await pane.find({ type: 'Button', key: `decision-${key('IC-21')}` }))?.text).toEndWith('· go ahead')
  expect((await pane.find({ type: 'Button', key: 'send-answers' }))?.text).toBe('Send 2 answers to Claude')

  const band = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect((await band.find({ type: 'Text', text: /wait for you/ }))?.text).toBe(
    'Just-DNA-Lite v0.6: 20 decisions wait for you · 2 answers not sent yet',
  )
  await band.unmount()

  await pane.press({ key: 'send-answers' })
  for (let n = 0; n < 50 && submitted.length === 0; n += 1) await Promise.resolve()
  expect(submitted).toHaveLength(1)
  // the person pressed it: their own words, not the plugin's
  expect(submitted[0]!.origin).toEqual({ kind: 'plugin', name: 'manuscript-skills', asUser: true })
  expect(submitted[0]!.text).toContain(`run folder ${RUN}`)
  expect(submitted[0]!.text).toContain(`Go ahead:\n- IC-21 (4.2 Production catalog (Table 4)): ${whole.summary} Suggested: ${whole.action}`)
  expect(submitted[0]!.text).toContain(`Leave as it is:\n- IC-1: ${held[0]!.summary}`)
  expect(await pane.find({ type: 'Button', key: 'send-answers' })).toBeUndefined()
  expect((await pane.find({ type: 'Button', key: `decision-${key('IC-21')}` }))?.text).toEndWith('· go ahead, sent')

  // an answer in the person's own words goes through the prompt box
  await pane.press({ key: `decision-${key('IC-2')}` })
  await pane.press({ key: `write-${key('IC-2')}` })
  expect(filled).toEqual([
    `On decision IC-2 of the Just-DNA-Lite v0.6 manuscript run (${RUN}), "${held[1]!.summary}": `,
  ])
  expect((await pane.find({ type: 'Button', key: `decision-${key('IC-2')}` }))?.text).toEndWith('· answered in the chat')
  expect((await pane.find({ type: 'Text', text: /wait for you$/ }))?.text).toBe('19 of 22 decisions wait for you')

  // a decision asked in a session of its own: Claude is asked, as the person, to start one titled with the paper
  await pane.press({ key: `decision-${key('IC-3')}` })
  await pane.press({ key: `session-${key('IC-3')}` })
  for (let n = 0; n < 50 && submitted.length < 2; n += 1) await Promise.resolve()
  expect(submitted[1]!.origin).toEqual({ kind: 'plugin', name: 'manuscript-skills', asUser: true })
  expect(submitted[1]!.text).toStartWith('Start a new Claude Code session that asks me about decision IC-3 of the Just-DNA-Lite v0.6')
  expect(submitted[1]!.text).toContain(`"Just-DNA-Lite: a Local-First Platform", called Just-DNA-Lite v0.6 here`)
  expect((await pane.find({ type: 'Button', key: `decision-${key('IC-3')}` }))?.text).toEndWith('· asked in a new session')
  expect((await pane.find({ type: 'Text', text: /wait for you$/ }))?.text).toBe('18 of 22 decisions wait for you')
  await pane.unmount()
})

// The dashboard's inventory, shaped like the Paper 1 v0.6 run's: the adjudication's decisions link the stages'
// `decision: true` findings, which the To-do tab then lists under the decision's ID, not their own.
const INVENTORY = {
  findings: [
    { id: 'IC-11', summary: 'Consent of a named author', section: 'Ethics Statement', quote: 'with her consent', action: 'Confirm with her.', decision: true },
    { id: 'PF-7', summary: 'Names on the figures', section: 'Figures 1b, 2 and 3', decision: true },
    { id: 'RP-12', summary: 'No licence for the data', section: 'Data Availability', action: 'Choose a licence.', decision: true },
    { id: 'RP-11', summary: 'No licence for the code', section: 'Code Availability', decision: true },
    { id: 'PF-3', summary: 'Say what the platform is not', section: '5.3 Platform Philosophy', decision: true },
    { id: 'PF-9', summary: 'Dismissed by the adjudication', decision: true, assessment: 'dismissed' },
    { id: 'IC-1', summary: 'A number does not add up', decision: false },
  ],
  decisions: [
    { id: 'D1', summary: "Livia Zaharia's consent: confirm it, or narrow the consent sentence.", finding_ids: ['IC-11'] },
    { id: 'D2', summary: 'Keep the names on the figures?', finding_ids: ['PF-7'] },
    { id: 'D5', summary: 'Choose a licence for the curated data and the code.', finding_ids: ['RP-12', 'RP-11'] },
  ],
  changes: [],
}

test('the pane lists the decisions the To-do tab lists, and the marks file sits beside the manuscript', () => {
  const found = summarizeFindings(INVENTORY)!
  // the adjudication's decisions, then a stage's own decision none links; a dismissed one is not the authors' to make
  expect(found.decisions.map(one => one.id)).toEqual(['D1', 'D2', 'D5', 'PF-3'])
  expect(found.decisions[2]).toEqual({
    id: 'D5',
    summary: 'Choose a licence for the curated data and the code.',
    findingIds: ['RP-12', 'RP-11'],
    section: 'Data Availability, Code Availability',
    detail: undefined,
    action: 'Choose a licence.',
    quote: undefined,
  })
  expect(found.decisions[0]).toMatchObject({ section: 'Ethics Statement', quote: 'with her consent', action: 'Confirm with her.' })
  // a stage's own findings.json has no adjudicated decisions: its `decision: true` findings, as before
  expect(summarizeFindings(FINDINGS)!.decisions).toEqual([
    { id: 'IC-2', summary: 'Which journal comes first', findingIds: ['IC-2'], section: undefined, detail: undefined, action: undefined, quote: undefined },
  ])

  expect(marksPath(runJson())).toBe(`${PROJECT}/paper1-just-dna-lite.todo.json`)
  // a connected manuscript's in the project folder, named after its reading copy, as runs.py handover puts the dashboard
  const remote = runJson()
  remote.inputs = [{ original: `${PROJECT}/.connected/paper.docx`, snapshot: 'inputs/01-paper.docx', remote: 'gdoc:abc' }]
  expect(marksPath(remote)).toBe(`${PROJECT}/paper.todo.json`)
  expect(marksPath({ ...runJson(), inputs: [] })).toBeNull()
})

test('the Decisions pane shares the authors\' marks with the dashboard\'s To-do tab', async ($, on) => {
  const RUN_ID = '20261027T125139Z-488af17b'
  const TODO = `${PROJECT}/paper1-just-dna-lite.todo.json`
  const mark = (id: string, kind: string, chosen: string, marked_at: string, reason = '', run_id = RUN_ID) => ({
    run_id, kind, id, mark: chosen, reason, marked_at, summary: `What ${id} said`, section: '', category: '', quote: null,
    action: '', before: null, after: null, anchor: null, finding_ids: [],
  })
  const saved = {
    schema_version: 1,
    manuscript: 'paper1-just-dna-lite.md',
    marks: [
      // an earlier run's mark on its own D1, which says nothing about this run's
      mark('D1', 'decision', 'approved', '2026-10-20T09:00:00.000Z', '', '20261020T090000Z-0badc0de'),
      // the To-do tab's mark on D2, and on a problem the pane does not list
      mark('D2', 'decision', 'redundant', '2026-10-27T13:40:00.000Z', 'The names stay; she agreed.'),
      mark('PR-4', 'problem', 'approved', '2026-10-27T13:41:00.000Z'),
    ],
  }
  const data = runJson('completed', 'completed')
  data.skills['manuscript-dashboard'] = { ...empty, status: 'completed' }
  const version = { n: 1 }
  const files = new Map<string, string>([
    [`${RUN}/run.json`, JSON.stringify(data)],
    [`${RUN}/manuscript-dashboard/findings.json`, JSON.stringify(INVENTORY)],
    [TODO, `${JSON.stringify(saved, null, 2)}\n`],
  ])
  const submitted: { text: string }[] = []
  const toasts: string[] = []
  folder(on, files, version)
  mock.clock(on, { now: Date.parse(at(59)) })
  mock.store(on)
  mock.env(on, { HOME: '/home/user' })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))
  on('prompt.submit', (_, e) => (submitted.push(e), { text: e.text }))
  const answer = await $.command.run({ ...TYPED, args: RUN })
  expect(answer.text).toContain(`4 decisions for the authors, 1 of them marked in ${TODO}.`)

  const key = (id: string) => `${RUN_ID}:Dashboard:${id}`
  const row = async (ui: { find: (q: { type: string; key: string }) => Promise<{ text?: string } | undefined> }, id: string) =>
    (await ui.find({ type: 'Button', key: `decision-${key(id)}` }))?.text
  const marks = () => (JSON.parse(files.get(TODO)!) as MarksFile).marks
  const pane = await $.ui.mount({ ...DECISIONS, surface: 'desktop' })
  // D2, marked in the To-do tab, counts as answered and shows the mark with its reason
  expect((await pane.find({ type: 'Text', text: /wait for you$/ }))?.text).toBe('3 of 4 decisions wait for you')
  expect(await row(pane, 'D2')).toEndWith('· marked redundant: “The names stay; she agreed.”')
  expect(await row(pane, 'D1')).toEndWith("Livia Zaharia's consent: confirm it, or narrow the consent sentence.")
  await pane.press({ key: `decision-${key('D2')}` })
  expect(
    await pane.find({ type: 'Text', text: 'Marked redundant on 27 Oct 2026 in paper1-just-dna-lite.todo.json: “The names stay; she agreed.”' }),
  ).toBeDefined()
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({ ...BAND, surface })
    expect((await band.find({ type: 'Text', text: /wait for you/ }))?.text).toBe('Paper 1 just-dna-lite v0.6: 3 decisions wait for you')
    await band.unmount()
  }

  // Go ahead marks D1 approved in the file, with what the decision said, as the To-do tab's markOf does; every other
  // mark stays, the oldest first
  await pane.press({ key: `decision-${key('D1')}` })
  await pane.press({ key: `go-ahead-${key('D1')}` })
  expect(marks().map(one => `${one.run_id.slice(0, 8)}:${one.kind}:${one.id}:${one.mark}`)).toEqual([
    '20261020:decision:D1:approved',
    '20261027:decision:D2:redundant',
    '20261027:problem:PR-4:approved',
    '20261027:decision:D1:approved',
  ])
  expect(marks().at(-1)).toEqual({
    run_id: RUN_ID,
    kind: 'decision',
    id: 'D1',
    mark: 'approved',
    reason: '',
    marked_at: '2026-10-27T13:59:00.000Z',
    summary: "Livia Zaharia's consent: confirm it, or narrow the consent sentence.",
    section: 'Ethics Statement',
    category: '',
    quote: 'with her consent',
    action: 'Confirm with her.',
    before: null,
    after: null,
    anchor: null,
    finding_ids: ['IC-11'],
  })
  expect(JSON.parse(files.get(TODO)!).manuscript).toBe('paper1-just-dna-lite.md')
  expect(await row(pane, 'D1')).toEndWith('· go ahead')
  expect((await pane.find({ type: 'Text', text: /wait for you$/ }))?.text).toBe('2 of 4 decisions wait for you')

  // Leave as is marks PF-3, a stage's own decision, redundant; Undo takes the mark back out of the file
  await pane.press({ key: `decision-${key('PF-3')}` })
  await pane.press({ key: `leave-${key('PF-3')}` })
  expect(marks().find(one => one.id === 'PF-3')).toMatchObject({ kind: 'decision', mark: 'redundant', section: '5.3 Platform Philosophy' })
  await pane.press({ key: `undo-${key('PF-3')}` })
  expect(marks().find(one => one.id === 'PF-3')).toBeUndefined()

  // leaving D2 as is marks it anew over the To-do tab's mark, its reason kept; Undo puts that mark back as it was
  await pane.press({ key: `leave-${key('D2')}` })
  expect(marks().find(one => one.id === 'D2' && one.run_id === RUN_ID)).toMatchObject({
    mark: 'redundant',
    reason: 'The names stay; she agreed.',
    marked_at: '2026-10-27T13:59:00.000Z',
  })
  expect(await row(pane, 'D2')).toEndWith('· leave as is: “The names stay; she agreed.”')
  await pane.press({ key: `undo-${key('D2')}` })
  expect(marks().find(one => one.id === 'D2' && one.run_id === RUN_ID)).toEqual(saved.marks[1])
  expect(await row(pane, 'D2')).toEndWith('· marked redundant: “The names stay; she agreed.”')

  // the answers still go to Claude in one message, which says where they are marked
  await pane.press({ key: 'send-answers' })
  for (let n = 0; n < 50 && submitted.length === 0; n += 1) await Promise.resolve()
  expect(submitted[0]!.text).toContain(`Go ahead:\n- D1 (Ethics Statement): Livia Zaharia's consent`)
  expect(submitted[0]!.text).toContain(`They are marked in ${TODO} too (go ahead as approved, leave as redundant)`)
  expect(await row(pane, 'D1')).toEndWith('· go ahead, sent')

  // the To-do tab marks D1 again later: the row shows its mark beside the answer sent
  const later = mark('D1', 'decision', 'redundant', '2026-10-27T14:10:00.000Z', 'On reflection, no.')
  files.set(TODO, JSON.stringify({ ...saved, marks: marks().map(one => (one.id === 'D1' && one.run_id === RUN_ID ? later : one)) }))
  version.n = 2
  await $.command.run({ ...TYPED, args: RUN })
  expect(await row(pane, 'D1')).toEndWith('· go ahead, sent · marked redundant: “On reflection, no.”')

  // a file that does not read as marks is never written over
  files.set(TODO, '{"schema_version": 1, "marks": [')
  version.n = 3
  await pane.press({ key: `decision-${key('D5')}` })
  await pane.press({ key: `leave-${key('D5')}` })
  expect(files.get(TODO)).toBe('{"schema_version": 1, "marks": [')
  expect(toasts).toContain("paper1-just-dna-lite.todo.json does not read as the To-do tab's marks, so the answer is kept in this session only.")
  expect(await row(pane, 'D5')).toEndWith('· leave as is')
  await pane.unmount()
})

test('before the dashboard lists the decisions, the pane neither reads nor writes the marks file', async ($, on) => {
  const TODO = `${PROJECT}/paper1-just-dna-lite.todo.json`
  const files = new Map<string, string>([
    [`${RUN}/run.json`, JSON.stringify(runJson('completed', 'completed'))],
    [`${RUN}/manuscript-integrity-check/findings.json`, JSON.stringify(FINDINGS)],
  ])
  folder(on, files, { n: 1 })
  mock.clock(on, { now: Date.parse(at(59)) })
  mock.store(on)
  mock.env(on, { HOME: '/home/user' })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))
  await $.command.run({ ...TYPED, args: RUN })

  const key = '20261027T125139Z-488af17b:Integrity check:IC-2'
  const pane = await $.ui.mount({ ...DECISIONS, surface: 'terminal' })
  expect(await pane.find({ type: 'Text', text: /To-do tab saves/ })).toBeUndefined()
  await pane.press({ key: `decision-${key}` })
  await pane.press({ key: `leave-${key}` })
  expect((await pane.find({ type: 'Button', key: `decision-${key}` }))?.text).toEndWith('· leave as is')
  expect(files.has(TODO)).toBe(false)
  await pane.unmount()
})
