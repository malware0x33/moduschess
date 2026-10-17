# Vendored Stockfish

- **Version:** Stockfish 19 (release tag `sf_19`, published 2026-09-05)
- **Release URL:** https://github.com/official-stockfish/Stockfish/releases/tag/sf_19
- **Asset:** https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip
- **Local file:** `bin/stockfish.exe` (extracted from `stockfish/stockfish-windows-x86-64-universal.exe`)

Note: as of Stockfish 19 the per-ISA Windows asset (e.g. `stockfish-windows-x86-64-avx2.zip`)
was replaced by a single universal x86-64 build with runtime CPU-feature dispatch. The
universal binary was verified via UCI handshake (`id name Stockfish 19` / `uciok`).

The binary is excluded from git via `.gitignore` (`bin/*.exe`) — re-download from the
release URL above if it is missing.
