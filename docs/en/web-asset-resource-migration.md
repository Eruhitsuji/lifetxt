# Web Asset Resource Migration

Issue: #367

The current Web bundle is a single `HTML_PAGE` compatibility value in
`lifetxt.web_assets`. The migration contract is to make a packaged resource the
source of truth while retaining `lifetxt.webapp.HTML_PAGE` as the public
compatibility value and preserving the `surface_runtime` pristine/rebound
split.

The required artifact checks are: editable import, wheel install, sdist
install, byte-for-byte resource comparison, and dependency-free core import.
No frontend toolchain or route refactor is permitted. The implementation must
use the existing setuptools package boundary and add an explicit resource
inclusion check before the large Python literal is removed.
