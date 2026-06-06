# Project Working Rules

These rules are part of the project workflow. Follow them before finishing any change that touches the desktop app, Windows EXE, packaging, release artifacts, or PR documentation.

## Windows Release Gate

- Treat Windows Smart App Control blocking as a release-blocking issue, not a cosmetic warning.
- Never present an unsigned EXE as a formal review or cross-machine release.
- Do not use `-SkipSignature` by itself. Unsigned local test builds must also pass `-AllowUnsignedLocalTestBuild`, and the final response must clearly call them unsigned local test builds.
- Before saying an EXE is ready for reviewers or other machines, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\packaging\verify-release-signature.ps1 -AllBinaries
```

- If signature verification fails or no trusted OV/EV code-signing certificate is available, say so plainly and do not claim the package will run on all Windows machines.
- For formal submission/cross-machine release, use `.\packaging\verify-release-signature.ps1 -RequirePublicPublisher` so self-signed or local test certificates are rejected.
- A self-signed certificate, icon change, manifest edit, filename change, zip file, or code change does not solve Smart App Control for other users. The real fix is trusted Authenticode signing plus normal reputation.
- For the current developer machine only, run `.\packaging\trust-local-test-publisher.ps1 -SignCurrentBuild -RefreshReleaseZip` after rebuilding an EXE so the root EXE and release zip EXE at least verify as `Valid` for the current Windows user.

## Desktop Overlay Regression Checks

- After touching `src/simultaneous_interpreter/desktop_overlay.py`, check that the floating button can be dragged, the subtitle panel can be dragged, and exit leaves no blank white window.
- Run the overlay tests:

```powershell
python -m pytest tests\test_desktop_overlay.py
```

## Required Validation

- Run `python -m pytest` and `python -m ruff check .` before publishing code changes, unless the blocker is explicitly documented.
- Update README and PR documentation when behavior, packaging, dependencies, or release steps change.
