# Implementation Plan

- [ ] 1. Add --version/-V flag to build_parser
  - Register via argparse action="version" with lifetxt.__version__
  - Observable completion: `python -m lifetxt --version` exits 0 and prints the version
  - _Requirements: 1.1, 1.2, 1.3_
- [ ] 2. Add regression test
  - _Requirements: 1.1, 1.2, 1.3_
