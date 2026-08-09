# Implementation Plan

- [x] 1. Implement the shared fuzzy-matching primitive (lifetxt/fuzzy_search.py) with unit tests
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
- [x] 2. Wire --fuzzy into CLI search, rejecting it together with --regex
  - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4_
- [x] 3. Wire fuzzy into filter_items() for the shared text filter
  - _Requirements: 2.1, 2.2, 3.1_
- [x] 4. Wire --fuzzy into CLI find / global_search(), with exact-before-approximate ranking per entity type
  - _Requirements: 2.1, 2.2, 4.1, 4.2, 4.3_
- [x] 5. Wire fuzzy=true into GET /api/items
  - _Requirements: 2.1, 2.2, 5.1, 5.2, 5.3_
- [x] 6. Document --fuzzy and fuzzy=true in English and Japanese CLI/Web docs
  - _Requirements: 3.1, 4.1, 5.1_
- [x] 7. Live-verify against the real installed CLI and a real serve process
  - _Requirements: 2.1, 3.1, 3.2, 4.1, 4.2, 5.1_
