# Personal Context: AI Authoring and Usage Guide

This guide explains how a generative AI can build, maintain, and use lifetxt as
provider-independent Personal Context / a Personal DB. It defines an authoring
and usage policy, not a new file format, schema, record kind, query language, or
AI-provider contract.

The core idea is simple:

```text
Chat / PDF / ZIP / Docs / Code / Images / other sources
                         |
                         v
                  Generative AI
             read / interpret / ask
                         |
                         v
              durable personal meaning
                         |
                         v
                      lifetxt
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          Bootstrap   Maintain    Consume
```

The AI is replaceable intelligence and interface. lifetxt is the durable,
user-owned context layer.

For MCP setup and the smaller conversation-to-proposal Personal AI Memory
pattern, see [AI Integration](./ai-integration.md#10-personal-ai-memory).

## 1. What belongs in Personal Context

Use this practical promotion rule:

> Would this information still be useful to another session, another AI, or
> the user at a later date?

If yes, it is a Personal Context candidate. If it only helps explain one source
or one current turn, keep it in the source/search/RAG layer instead.

| Category | Typical durable meaning |
| --- | --- |
| Profile | role, specialty, affiliation, stable identity context |
| Preference | preferred tools, formats, work style, recurring likes/dislikes |
| Value | durable decision principles or priorities |
| Skill | capabilities and meaningful experience |
| Goal | medium- or long-term objectives |
| Project | continuing activities and responsibilities |
| Relationship | useful person or organization context |
| Decision | important decisions and rationale |
| Current context | state that remains relevant beyond one turn |
| History | important past facts worth future reference |

Normally do **not** promote these into Personal Context:

- full chat transcripts;
- full PDF/document contents;
- every file from a ZIP/archive;
- RAG chunks, embeddings, or search indexes;
- transient small talk;
- one-turn facts that will stop mattering immediately;
- unsupported AI personality/profile inference;
- a duplicate of a fact already represented adequately.

The responsibility boundary is:

```text
RAG / source lookup: "What does the source say?"
lifetxt:             "What durable meaning does this have for the user?"
AI:                  "What should we conclude or do from those facts?"
```

## 2. Let the AI/client handle source formats

The input format does not need to be a lifetxt feature. A capable chat AI or
agent may read a PDF, inspect a ZIP, execute code, inspect a repository, parse a
spreadsheet, or use any other tools available to it.

For this workflow, lifetxt does **not** need built-in PDF, ZIP, DOCX, OCR,
embedding, vector-database, or provider-specific ingestion code. The AI/client
understands the source; lifetxt receives only the durable structured result.

This keeps the workflow useful as AI clients gain support for new source types
without requiring a corresponding Format change.

When useful, retain lightweight provenance with the existing `source:` field:

```text
source:chat
source:resume.pdf
source:resume.pdf#page=2
source:research.zip#README.md
```

These values are coarse references, not a new structured provenance contract.
Keep the original document or archive in its appropriate source system when it
still matters; do not mirror it into `life.txt` merely to preserve evidence.

## 3. Author records with existing Format 1.0 concepts

A durable personal fact is normally an ordinary `N` (Note) record. For a fact
about the workspace owner, use `person:self`. Use ordinary freeform `tag:`
values to make the intent legible.

A useful record shape is:

```text
[N] N "Prefers CLI tools" id:ctx_pref_cli person:self tag:preference source:chat updated:2026-09-01
[N] N "Uses Python regularly" id:ctx_skill_python person:self tag:skill source:resume.pdf updated:2026-09-01
```

`profile`, `preference`, `value`, `skill`, `goal`, `project`, `relationship`,
`decision`, and similar tag values are **conventions**, not new mandatory
schema and not new automatically first-class Query fields.

`id:` is strongly recommended for durable Personal Context because explanation,
links, corrections, and supersession work best when a record has a stable ID.
`updated:` is optional, but the Personal Context staleness calculation can only
age a record when an `updated:` value exists. `source:` is also optional at the
Format level, but `context health` reports Personal Context records with no
source so that provenance gaps remain visible.

### Context is not the same as action

Use another existing record kind when the information naturally represents
something else. Do not force every personal record into `N`.

```text
[N] N "Wants to improve English ability" id:ctx_goal_english person:self tag:goal source:chat
[ ] T "Study TOEIC material for 30 minutes" project:english
```

The first line is reusable context about a goal. The second line is an action.
Likewise, use `E` for a calendar event, `J` for a dated journal/history entry,
and `S` for presence/current-status information when those existing meanings
fit better.

### Prefer atomic, independently correctable facts

One record should normally contain one coherent piece of meaning that could be
corrected, superseded, retired, or referenced independently.

Avoid a giant profile note:

```text
[N] N "Profile" person:self
| Uses Python, prefers CLI tools, is working on Project A, and wants to learn English.
```

Prefer independently maintainable facts:

```text
[N] N "Uses Python regularly" id:ctx_skill_python person:self tag:skill source:chat
[N] N "Prefers CLI tools" id:ctx_pref_cli person:self tag:preference source:chat
[N] N "Works on Project A" id:ctx_project_a person:self tag:project source:chat
[N] N "Wants to improve English ability" id:ctx_goal_english person:self tag:goal source:chat
```

Do not over-split a single coherent fact into unreadable fragments. The test is:
"Could this fact reasonably change or need correction without changing the
others?"

## 4. Do not silently turn AI inference into durable fact

An AI may extract a directly supported fact from a user statement or source.
It must not silently promote an unsupported interpretation into authoritative
Personal Context.

For example, a source may support:

```text
Uses Python regularly
```

That does not automatically support:

```text
Python is the user's favorite programming language
```

If an inference would be useful as Personal Context, ask the user to confirm it
first. Once confirmed, it can be handled like any other explicit candidate.

This guide deliberately does not introduce `assertion:`, `confidence:`, or
`subject:` vocabulary. Those concepts remain deferred until real use justifies
a stable Format/Query contract.

## 5. Lifecycle: Bootstrap -> Maintain -> Consume

### 5.1 Bootstrap

Bootstrap creates a small initial Personal Context from the material currently
available to the AI. It is not an attempt to model the user's entire life.

Recommended sequence:

```text
DISCOVER    Read existing Personal Context if present.
SCOPE       Choose useful context domains for this task/user.
INGEST      Read the sources the AI/client can understand.
EXTRACT     Select durable, repeatedly useful personal meaning.
ATOMIZE     Split it into independently correctable facts.
CLASSIFY    Map facts to existing kinds + person/tags/source.
VERIFY      Confirm ambiguous or inferred candidates with the user.
RECONCILE   Detect duplicates, conflicts, and supersession.
REVIEW      Show or stage proposed records for human review.
VALIDATE    Check the resulting lifetxt workspace/context.
```

A useful initial subset is:

- profile / identity context;
- preferences;
- skills / capabilities;
- goals;
- active projects / responsibilities.

Add values, relationships, decisions, and important history later when they
become useful. Starting small makes review easier and avoids filling the file
with speculative or low-value context.

For an ordinary chat AI with no lifetxt connection, a simple request is enough:

```text
Build a small lifetxt Personal Context from this conversation and the files I
provide. Keep only durable facts that will be useful in future sessions. Use
ordinary Format 1.0 records, prefer one independently correctable fact per
record, do not store unsupported inference, and show me the proposed records
before I save them.
```

The user can save the reviewed result as `personal.life.txt` and validate it:

```sh
lifetxt check personal.life.txt
lifetxt context health personal.life.txt
```

### 5.2 Maintain

Personal Context should grow during normal use rather than through repeated
full rebuilds.

When a later conversation or source contains a useful durable fact:

1. compare it with current context;
2. do nothing if it is already represented adequately;
3. add a new atomic record if it is genuinely additive;
4. treat a changed fact as a correction/supersession rather than a duplicate;
5. review the proposed change before authoritative mutation when appropriate.

The deterministic toolkit can inspect current health:

```sh
lifetxt context health personal.life.txt
lifetxt context why ctx_pref_cli personal.life.txt
```

When a stored fact has changed, stage a history-preserving correction:

```sh
lifetxt memory correct ctx_pref_cli "Now prefers GUI tools for daily work" personal.life.txt --source chat
lifetxt proposal list
lifetxt proposal show PROPOSAL_ID
lifetxt proposal accept PROPOSAL_ID
```

The correction proposal points back to the old record with the existing
`corrects:<old-id>` convention. The previous record remains inspectable, while
the toolkit treats it as superseded after the correcting record is accepted.

For an MCP/agent client, `--profile assist` provides the same proposal-first
boundary: read tools are available, while the only additional write capability
is `stage_proposal`. MCP is useful automation, not a requirement for this
lifecycle.

### 5.3 Consume

Personal Context becomes valuable when another session or another AI can use it
without rediscovering the same facts.

Typical uses include:

- personalize answers using known preferences and constraints;
- recover context in a new AI/session;
- plan against current goals and projects;
- recommend tools or methods consistent with known skills and preferences;
- retrieve relevant person/project context before starting work;
- compare a new choice with prior decisions and rationale;
- build a bounded context projection for an AI instead of sending every record.

Use ordinary search/query surfaces when a narrow lookup is sufficient:

```sh
lifetxt search "CLI" personal.life.txt
lifetxt query "kind:N person:self tag:preference" personal.life.txt
lifetxt decisions personal.life.txt
```

For a bounded, deterministic AI-facing projection, use a Context Capsule:

```sh
lifetxt context capsule personal.life.txt --pretty
lifetxt context capsule personal.life.txt --tag goal --tag project --pretty
```

The capsule is a read-only projection with a deterministic revision. It is not a
second source of truth. By default it excludes stale and superseded Personal
Context records, which makes it a better handoff surface than blindly sending
all historical records to every model.

## 6. Reconcile before appending

An AI maintaining existing Personal Context should classify new information as
one of these cases:

| Case | Action |
| --- | --- |
| Same fact already exists | Do not create a duplicate |
| New independent fact | Add a new atomic candidate |
| Existing fact gains useful independent detail | Add/refine only the needed meaning |
| Existing fact changed | Correct/supersede the old record |
| Sources conflict or meaning is unclear | Ask the user before promoting |
| Old fact is merely historical | Keep history, but stop treating it as current/default context |

The goal is a Personal Context store that remains explainable and maintainable,
not an append-only log where every past statement is treated as permanently
true.

## 7. Start with one file; split only when useful

The simplest recommended layout is:

```text
personal.life.txt
```

That is enough for a useful Personal DB. Do not make initial adoption depend on
a large directory taxonomy.

When the context becomes large, normal multi-file workspace support can split it
for human organization:

```text
personal/
  profile.life.txt
  preferences.life.txt
  projects.life.txt
  decisions.life.txt
  history.life.txt
```

This is only a workspace/file organization choice. It does not introduce new
Personal DB storage semantics, and all files can still be read together by
lifetxt's multi-file surfaces.

## 8. Worked scenarios

### 8.1 Chat-only bootstrap

A user starts with no Personal Context and asks a chat AI to help build one.
The AI asks a bounded set of questions about profile, preferences, skills,
goals, and active projects. It extracts only explicit durable facts, presents a
small reviewed set of `N` records, and the user saves them to
`personal.life.txt`.

The next session can read that file instead of asking the same background
questions again.

### 8.2 Document-assisted bootstrap (PDF / ZIP / repository)

The user uploads a resume PDF and a project ZIP to a capable chat AI. The AI
reads the PDF, inspects useful files inside the archive, and extracts only
long-lived meaning such as durable skills, project responsibilities, or stated
goals.

It may produce records such as:

```text
[N] N "Uses Python regularly" id:ctx_skill_python person:self tag:skill source:resume.pdf
[N] N "Maintains Project A" id:ctx_project_a person:self tag:project source:research.zip#README.md
```

The PDF and ZIP remain source material. **lifetxt itself did not parse either
file in this workflow.** If the AI client can understand a future file type,
the same Personal Context authoring policy still applies.

### 8.3 Ongoing maintenance and correction

A stored record says the user prefers one work style. Months later the user
explicitly says their preference has changed.

The AI should not append a second contradictory preference and leave both as
current. It identifies the existing record, proposes a correction with
`lifetxt memory correct` (or an equivalent reviewed/manual change), and
preserves the previous record as history through `corrects:`.

`lifetxt context health` then classifies the old record as superseded instead of
silently treating both values as current.

### 8.4 Cross-session / cross-provider reuse

A later AI client needs to help plan work. It reads a bounded Context Capsule
containing current goals, projects, and preferences, then uses those facts to
shape its plan.

The same `personal.life.txt` can be used by a different MCP client, CLI-driven
agent, local model, or ordinary chat workflow. Provider-specific memory is not
the durable store; lifetxt is.

## 9. Review and validation checklist for AI authors

Before proposing or saving Personal Context, an AI should check:

- Is the information durable enough to matter later?
- Is it supported explicitly by the user/source rather than guessed?
- Is the source material being summarized into meaning rather than copied?
- Is the fact independent enough to correct later?
- Does an equivalent record already exist?
- Is this really a Note, or does an existing `T`/`E`/`J`/`S` kind fit better?
- Does a durable record have a useful `id:`?
- Is a lightweight `source:` reference available?
- Should an existing record be corrected/superseded instead of duplicated?
- Has the user had a chance to review AI-generated authoritative changes?

Finally, validate the actual file rather than trusting the generated text:

```sh
lifetxt check personal.life.txt
lifetxt context health personal.life.txt
```

## 10. Non-goals

This guide does not add or require:

- a Personal DB-specific database engine or record type;
- built-in PDF/ZIP/DOCX/OCR ingestion;
- RAG, embeddings, vector storage, or bulk source mirroring;
- provider SDKs or provider-specific memory APIs;
- first-class `subject:`, `assertion:`, `confidence:`, or category fields;
- promotion of the example tag values into mandatory Query vocabulary;
- automatic unreviewed authoritative AI writes;
- a requirement to use MCP.

The intended architecture remains:

```text
AI/client   understands sources and proposes meaning
lifetxt     stores durable, inspectable, user-owned context
human       remains the authority for what becomes trusted personal context
```
