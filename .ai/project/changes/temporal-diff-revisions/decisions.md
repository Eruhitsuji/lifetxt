# Decisions

## D1: Publish temporal-diff-v1

Semantic comparison is an independently useful read contract with different
categories and completeness semantics, so it receives its own schema and
capability while composing temporal-thread-v1 inputs.

## D2: Use stable semantic identities

Items use IDs and selected stable fields, edges use relation/source/target, and
warnings use relation/source/target/reason. Evidence remains in output but does
not turn one continuing warning into a false resolve plus introduction.

## D3: Be conservative about bounds

Known truncation and a derived list exactly at its limit prevent a complete
claim. This favors explicit uncertainty over a false full comparison.
