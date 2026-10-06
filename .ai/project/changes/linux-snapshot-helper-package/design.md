# Helper distribution

Explicit build-time script compiles fixed trusted source using target system headers. It installs a fixed-name executable and protocol/arch/libc/source/binary SHA-256 manifest beside the module, never via PATH. No runtime compiler/fetch or mandatory pip dependency. A mismatched partly installed pair is unavailable. Current target Linux x86_64/glibc; other hosts remain unverified. Core wheels explicitly exclude native executable/manifest; source distributions retain C source and build script. Build operator uses --output for installed package directory. No new configuration setting; configuration completion rule is not applicable.

Runtime verifier/supervisor is #1118. Only trusted root/current-uid package directory/manifest/binary may be used; hashes prove consistency, not malicious-owner authenticity. Runtime install smoke will run after #1118.
