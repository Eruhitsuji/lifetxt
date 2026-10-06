# Decisions and self-review

- D1: Preserve the approved #1103 public HTTPS/443/GET, identity-only, default-disabled
  candidate. No runtime scope names, schemas, settings or destinations are published.
- D2: Keep object/provider opaque identity rules separate from strict URL parsing.
  Alias or credential changes never silently substitute authority.
- D3: Require validated IP connection binding and egress verification. DNS checks
  alone and inbound proxy trust cannot certify outbound routing/NAT/proxy safety.
- D4: Suppress entire URLs, including path capabilities, throughout all surfaces.
  Query stripping, local path redaction and no-store are not historical erasure.
- D5: Reuse compensated attachment transactions and exact CAS; transaction_id alone
  is not a network replay contract. Unknown commit is inspected before any retry.
- D6: Retain B-D as owner-gated plans. A concrete surface/destination and exact
  consumer wire/commit/replay contract are unresolved only for future runtime work.

## Implementer review findings

Four documentation gaps were corrected before verification:
1. A 30 s network deadline did not define the lifetime of blocking local commit.
   Section 7 now requires consumer-defined bounded supervised validation/commit,
   admission refusal and retained physical-worker capacity; it does not promise
   filesystem cancellation or invent a implemented commit timer.
2. Content-Disposition/URL basename and a pre-fetch root check could be mistaken
   for sufficient target safety. Sections 7/9 require generated create-only targets
   and mutation-boundary confinement/link checks through the existing writer.

3. Current authority now revalidates at connection/redirect/cancellation checkpoints
   and before delivery/commit; revocation stops work, without claiming byte recall.
4. Secret-free idempotency must not imply storing raw URLs or their correlatable
   digests. Section 9 requires non-secret locator identity/scoped opaque validators
   and rejects uncertain secret-bearing intent before replay enrollment.

The example is reserved public data and does not approve its destination.
Future N01-N17 are explicitly unimplemented/unrun. Final independent human
review is pending and must target the latest PR head.
