# Decisions

Maintainer explicitly approved optional context_token on the existing batch route, legacy compatibility, context409 precedence, retained CAS and separate UI work on 2026-10-10. DoR recorded on #1188 before code changes.

High assurance, justified M, complexity 8 (breadth2, dependency1, uncertainty1, test2, persistence risk2). Escalated assurance meets TASK_DECOMPOSITION for score7+. One contextual validation-to-write invariant cannot be split into independently safe partial guards; recovery already split into #1189. Executor ChatGPT, owner Eruhitsuji.

Phase implementation/integration; review viewpoints correctness, backward compatibility, persistence race and privacy; test viewpoints input/context mutation and late CAS, complete rejection, warnings and legacy clients; coding viewpoints shared Core/snapshot reuse and narrow endpoint branch; security viewpoints no token authority, no private error evidence, no auth bypass. No additional cost/service/auth/Format change. Independent implementation and integration reviews remain pending; implementer self-review is not their approval. Human merge only.
