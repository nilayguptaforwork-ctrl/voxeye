# Publishing voxeye to PyPI

**Status:** `voxeye` is **live on PyPI** (https://pypi.org/project/voxeye/) — first release
`0.1.0` published via GitHub Actions Trusted Publishing (OIDC, no tokens). The `pypi`
GitHub Environment and the PyPI trusted publisher are already configured, so cutting future
releases is the short flow below.

---

## Releasing a new version (the recurring flow)

> ⚠️ **The version comes from `pyproject.toml`, NOT from the git tag.** The release/tag is
> only the *trigger*; `uv build` stamps whatever `version = "..."` says in `pyproject.toml`.
> If you cut a release without bumping it, the workflow rebuilds the same version and PyPI
> **rejects it** ("file already exists" — PyPI versions are immutable). So **always bump
> `pyproject.toml` first.** Keep the tag and the `pyproject` version in sync (tag `vX.Y.Z`
> ↔ `version = "X.Y.Z"`).

1. **Bump the version** in `pyproject.toml` (`version = "0.2.0"`).
2. **Add a `CHANGELOG.md` entry** for the new version.
3. **Commit + push to `main`:**
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "Release 0.2.0"
   git push
   ```
4. **Cut the GitHub Release** (this fires the publish workflow):
   ```bash
   gh release create v0.2.0 --title "voxeye 0.2.0" --notes "…"
   ```
   The `publish` workflow builds, `twine check`s, and uploads to PyPI via Trusted
   Publishing — no tokens. Watch it: `gh run watch $(gh run list --workflow=publish.yml -L1 --json databaseId --jq '.[0].databaseId') --exit-status`.
5. **Verify:** `uv pip install --python /tmp/v voxeye==0.2.0` (in a fresh `uv venv /tmp/v`).

### Optional dry-run on TestPyPI first
The workflow also has a manual path: **Actions → publish → Run workflow → target `testpypi`**.
Requires a `testpypi` GitHub Environment + a TestPyPI trusted publisher (not yet set up). Use
it to rehearse a release without burning a real PyPI version.

### Want "just cut a tag" with no manual bump?
Switch to tag-derived versioning (`hatch-vcs`): the version is computed from the git tag, so
the tag becomes the single source of truth and the footgun above disappears. Ask and it's a
~5-line change (`dynamic = ["version"]` + `fetch-depth: 0` on checkout).

---

## How the automated publish is wired
- **Workflow:** `.github/workflows/publish.yml` — triggers on a published GitHub Release
  (→ PyPI) and on manual `workflow_dispatch` (→ TestPyPI or PyPI).
- **Trusted Publishing (OIDC):** no API tokens anywhere. Configured per index + GitHub
  Environment: PyPI publisher ↔ `pypi` environment (set up); TestPyPI ↔ `testpypi` (optional).
- Trusted-publisher fields (PyPI → Account → Publishing): Project `voxeye`, Owner
  `nilayguptaforwork-ctrl`, Repo `voxeye`, Workflow `publish.yml`, Environment `pypi`.

---

## Manual / no-CI fallback (local, needs an API token)

Everything below needs no PyPI account except the upload step.

```bash
cd voxeye
rm -rf dist && uv build                # build wheel + sdist
uvx twine check dist/*                 # metadata valid + README renders
tar tzf dist/voxeye-*.tar.gz           # sanity: src + README + LICENSE only, no secrets

# clean-install smoke test (no creds):
uv venv /tmp/voxeye-test
uv pip install --python /tmp/voxeye-test dist/voxeye-*.whl
/tmp/voxeye-test/bin/python -c "import voxeye; print(voxeye.__version__)"

# upload with a PyPI API token (username __token__):
uvx twine upload --repository testpypi dist/*   # dry-run on TestPyPI
uvx twine upload dist/*                          # production PyPI
```

---

## Notes
- **Versions are immutable on PyPI** — you can't re-upload or overwrite a version. Bump for
  every real re-publish; use TestPyPI for trial runs.
- The package ships `py.typed` (PEP 561); the sdist carries only `src/ + README + LICENSE`.
- Build artifacts (`dist/`) are git-ignored.
