# Philosophy and Long-Term Vision

This document explains why lifetxt exists and what principles should guide
its evolution. It is written for users deciding whether lifetxt fits how
they want to keep their own records, and for contributors deciding whether
a proposed feature belongs in the project.

It states intent and direction. It does not itself change any runtime
behavior, file format, API, schema, or MCP contract. Where this document
and `.ai/project/RULES.md`'s Design Principles disagree, `RULES.md` is
authoritative (see [Section 10](#10-product-principles-for-future-features)).

- [1. Why lifetxt exists](#1-why-lifetxt-exists)
- [2. An integrated record of life](#2-an-integrated-record-of-life)
- [3. Why text is the substrate](#3-why-text-is-the-substrate)
- [4. One record, many interfaces](#4-one-record-many-interfaces)
- [5. User ownership and portability](#5-user-ownership-and-portability)
- [6. External systems and the hub model](#6-external-systems-and-the-hub-model)
- [7. AI and Personal Context](#7-ai-and-personal-context)
- [8. Life Record, Life Context, Life Assistance](#8-life-record-life-context-life-assistance)
- [9. Privacy, selective recording, and disclosure](#9-privacy-selective-recording-and-disclosure)
- [10. Product principles for future features](#10-product-principles-for-future-features)
- [11. What lifetxt is not](#11-what-lifetxt-is-not)

---

## 1. Why lifetxt exists

Most software that helps people manage their lives is organized around one
category: a task manager, a calendar, a notes app, a journal, a habit
tracker. Each is usually a separate application, with its own storage,
its own account, and its own idea of what matters.

lifetxt starts from a different premise: tasks, events, deadlines,
reminders, habits, status, messages, notes, and journal entries are not
unrelated categories competing for a slot on your phone. They are different
views of the same thing -- a single person's life, considered across time.
The name is meant literally: **life** because the scope is broader than one
productivity category, and **txt** because the durable substrate is simple,
inspectable, portable text rather than any one application, service, or UI.

lifetxt is a text-native, user-owned foundation for recording and using
important information about a person's past, present, and future, across
tools and interfaces.

## 2. An integrated record of life

A useful way to think about what belongs in the record is a simple time
model:

```text
Past     = history / what happened
Present  = state / what is happening
Future   = intent / what should or may happen
```

A completed task, a logged work session, and a journal entry about a hard
day are all "past." A presence record showing you are in a meeting right
now is "present." A deadline, a habit's next occurrence, and a half-formed
plan are "future." lifetxt keeps these dimensions interoperable in one
record model instead of forcing your life to sort itself into application
boundaries such as "calendar," "todo," "notes," or "journal."

"Integrated life record" means integration around *your* life and the
relationships between your information -- a task can reference the
project it belongs to, a journal entry can reference the day's events, a
ticket's history can reference the person who raised it. It does not mean
indiscriminate collection of every possible datum about you; see
[Section 9](#9-privacy-selective-recording-and-disclosure).

## 3. Why text is the substrate

Plain text is not a convenience for CLI or editor users only. It is part
of the durability strategy:

- The record remains inspectable without a proprietary application --
  anyone can open it and read it.
- Standard tools -- editors, version control, diff, search, scripts,
  backups -- already know how to operate on it.
- A future lifetxt implementation, or an unrelated tool entirely, can
  still interpret or migrate the data, because it was never locked inside
  a binary format only one program understands.
- Users retain practical possession of their own records: nothing about
  reading or copying a `life.txt` file requires lifetxt's cooperation.

Text alone does not guarantee perfect future compatibility. `life.txt`
still has documented grammar and format semantics, and evolving that
grammar responsibly still requires the migration and compatibility rules
described in [the format specification](./life_txt_format_spec.md) and
[the format migration guide](./format-migration.md). Plain text lowers the
cost of that evolution; it does not eliminate the need for it.

## 4. One record, many interfaces

lifetxt intentionally supports several access surfaces at once:

```text
plain text editor
CLI
TUI
Web UI / API
AI / MCP / future agent interfaces
```

None of these is the one canonical human interface. Each is a way of
reading, presenting, or changing the same underlying data. Direct text
editing remains a legitimate, permanent access path -- you can always open
`life.txt` in any editor and understand or change what is there. That is
separate from the write-safety rule for lifetxt-managed mutations: when
the CLI, TUI, Web, or MCP surface performs an authoritative write, it goes
through this project's validated, atomic, revision-aware mutation
contracts, exactly as `.ai/project/RULES.md`'s Design Principles already
require, so that a concurrent edit is never silently lost.

The invariant that matters is that the underlying data and its semantics
stay inspectable and portable while any one interface can be replaced,
extended, or abandoned without taking your record down with it.

## 5. User ownership and portability

"Access anywhere" is broader than remote network access. lifetxt's
portability claim spans several dimensions:

- different devices and environments;
- different interfaces (editor, CLI, TUI, Web, AI);
- different software clients built against the same contracts;
- different AI providers;
- future interfaces that do not exist yet;
- long periods of time in which today's software may no longer exist.

This is not a promise of universal connectivity or guaranteed availability
-- lifetxt does not claim your record will always be reachable from
anywhere with no setup. The point is narrower and more durable: the record
should remain reusable on its own terms, without being structurally
trapped inside one client, one account, or one company's continued
existence.

This is the general principle behind a more specific one already stated
for AI integration (see [`ai-integration.md`](./ai-integration.md) and
[issue #500](https://github.com/Eruhitsuji/lifetxt/issues/500)):

```text
UI is replaceable.
Client is replaceable.
AI is replaceable.
Provider is replaceable.
Transport is replaceable.

Your life record is the durable layer.
```

## 6. External systems and the hub model

lifetxt does not try to replace email, calendars, chat, Git hosting,
CI/CD, issue trackers, or file storage. Those systems can remain
authoritative for their own domains. lifetxt's role is to be a hub:
integrating references, normalized summaries, relevant state, proposals,
and your own recorded meaning, rather than requiring a complete mirror of
every external data source.

A calendar event referenced from `life.txt` does not need every detail the
calendar provider stores; it needs enough for your record to stay useful
-- title, time, and a link back to the source of truth. A development
ticket's full comment history can stay in GitHub or GitLab while lifetxt
keeps a normalized, append-only local history of the parts that matter to
you. This keeps the record honest about what it actually owns versus what
it merely references.

## 7. AI and Personal Context

Generative AI can help in both directions:

```text
human language / external evidence
    -> interpretation
    -> proposal / structured capture
    -> lifetxt

lifetxt
    -> retrieval / context
    -> AI
    -> explanation / planning / suggestion
```

An AI client can help you turn a rough note into a well-formed record, or
turn your existing record into a daily briefing, a project summary, or a
suggested next action. What it should not do is become the place where
your long-lived context actually lives. If a model or a provider's memory
feature is the only place recording who you are and what you care about,
that context disappears the moment you switch tools, and no one but the
provider can inspect it.

> **AI should use your life context; it should not own it.**

[Issue #500](https://github.com/Eruhitsuji/lifetxt/issues/500) (provider-
independent AI integration) and
[issue #503](https://github.com/Eruhitsuji/lifetxt/issues/503) (Personal
Context Engine investigation) are concrete, AI-era applications of this
principle -- not the definition of what lifetxt is. The principle would
still hold if every AI product in use today were replaced tomorrow.

## 8. Life Record, Life Context, Life Assistance

A simple layering clarifies what depends on what:

```text
Life Record
    |
    v
Life Context
    |
    v
Life Assistance
```

- **Life Record** is the durable source: your tasks, events, notes,
  journals, status, and history, as they actually exist in `life.txt` and
  its configured sources.
- **Life Context** is the meaningful structure derived from that record --
  relationships between records, current state, relevant history for a
  given moment or question.
- **Life Assistance** is what any interface -- CLI, TUI, Web, automation,
  or AI -- can do with that context: search, review, plan, explain,
  propose, and act, always within the policies and permissions that apply
  to that surface.

The record must remain useful even if the assistance layer changes
completely. A person should be able to lose access to every current
lifetxt interface and AI integration and still have a real, usable record
of their own life sitting in plain text files.

## 9. Privacy, selective recording, and disclosure

"Integrated life record" must not be read as "collect everything
automatically." lifetxt's ownership model includes the right not to
record, and not to disclose:

- You decide what belongs in your record. Nothing is captured without an
  explicit action on your part -- a command, an edit, an accepted
  proposal.
- Private or sensitive data is not disclosed merely because it exists in
  your record. Visibility, workspace boundaries, and disclosure policy
  are deliberate, separate concerns from whether data is stored at all.
- Granting an AI client, a remote user, or an integration *access* or
  *permission* is a separate decision from *ownership*. You can permit
  narrow read access, or a proposal-only write path, without surrendering
  control over the underlying record.
- Provenance matters: a record that was proposed by an AI, imported from
  an external system, or entered by another person should stay
  distinguishable from what you entered yourself.

Data minimization, workspace boundaries, disclosure policy, and
provenance tracking are how this principle is actually enforced in the
software; this document states the intent that those mechanisms exist to
serve.

## 10. Product principles for future features

`.ai/project/RULES.md`'s Design Principles and Product Boundaries remain
the repository-authoritative, enforceable rules for what lifetxt does and
does not do. This document explains the reasoning and long-term direction
behind those rules in more accessible terms; it does not add new rules of
its own, and if the two ever appear to disagree, `RULES.md` wins.

When evaluating whether a new capability belongs in lifetxt, a useful
checklist is:

- Does this help preserve or use meaningful life information?
- Does it keep authoritative user data portable and inspectable?
- Does it unnecessarily bind the data model to one interface, provider,
  or transport?
- Can the capability be exposed consistently through multiple surfaces
  where appropriate?
- Does AI assist the user's record rather than becoming its owner or
  source of truth by accident?
- Does integration preserve privacy, provenance, and external systems'
  own authority over their own domains?
- Will the underlying record remain understandable if today's preferred
  client disappears?

## 11. What lifetxt is not

To keep this vision from overreaching, lifetxt explicitly does not claim
to be:

- A complete, autonomous "Life OS" that controls every external system on
  your behalf.
- A requirement that all life data must be collected or stored -- most of
  a life is, and should remain, unrecorded.
- A universal connectivity promise -- access anywhere means portability
  across devices, interfaces, clients, and time, not guaranteed network
  reachability from everywhere at all times.
- A replacement for email, calendars, chat, Git hosting, CI/CD, issue
  trackers, or file storage; see [Section 6](#6-external-systems-and-the-hub-model).
- A single-AI-provider product. See [Section 7](#7-ai-and-personal-context)
  and [`ai-integration.md`](./ai-integration.md).
