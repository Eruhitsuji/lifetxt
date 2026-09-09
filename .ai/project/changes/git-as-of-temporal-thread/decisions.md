# Decisions

## D1: Use committer time only

V1 fixes selection to committer timestamp so one cutoff cannot vary by an
implicit author/committer policy. The chosen policy is always in provenance.

## D2: Require an offset-aware timestamp

RFC3339 input with Z or an explicit offset avoids workspace-timezone and
end-of-day ambiguity. Bare dates remain out of scope.

## D3: Bound history and disclose incompleteness

Selection fails beyond its hard scan limit rather than silently choosing from
partial evidence. A shallow repository is detectable and cannot claim complete
history.
