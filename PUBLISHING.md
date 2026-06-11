# Publishing voxeye to PyPI

The release runbook. Steps **0–3 need no credentials** and are already verified; steps
**4–5 require a PyPI/TestPyPI account or trusted-publisher setup** (the credential gate).

> Name status: `voxeye` is currently **unclaimed** on both PyPI and TestPyPI — reserve it
> with the first upload (step 4/5).

---

## 0. Metadata (done — review before each release)
`pyproject.toml` is publish-ready: `name`, `version`, `description`, `readme`, `license`
+ `LICENSE` file, `requires-python`, `authors`, `keywords`, trove `classifiers`,
`project.urls` (Homepage/Repository/Docs/Issues/Changelog), and pinned runtime deps.
Bump `version` and add a `CHANGELOG.md` entry for each release. The package ships
`py.typed` (PEP 561).

## 1. Build  *(no creds)*
```bash
cd voxeye
rm -rf dist && uv build
```
Produces `dist/voxeye-<version>-py3-none-any.whl` and `.tar.gz`.

## 2. Validate  *(no creds)*
```bash
uvx twine check dist/*          # metadata valid + README renders on PyPI
tar tzf dist/voxeye-*.tar.gz    # sanity: src + README + LICENSE only, no .env/secrets
```

## 3. Clean-install smoke test  *(no creds)*
```bash
uv venv /tmp/voxeye-test
uv pip install --python /tmp/voxeye-test dist/voxeye-*.whl
/tmp/voxeye-test/bin/python -c "import voxeye; from voxeye import Observability, Redaction; print(voxeye.__version__)"
```

---

## 4. TestPyPI dry-run  *(needs TestPyPI auth — credential gate)*
Publish to TestPyPI first to confirm the real upload + render before touching PyPI.

**Option A — GitHub Actions (recommended, tokenless):** in TestPyPI, add this repo as a
[trusted publisher](https://docs.pypi.org/trusted-publishers/) for project `voxeye`, create
a GitHub Environment named `testpypi`, then run the **publish** workflow manually
(`workflow_dispatch` → target `testpypi`).

**Option B — local with a TestPyPI API token:**
```bash
uvx twine upload --repository testpypi dist/*
```
Then verify a real install from TestPyPI (deps come from real PyPI):
```bash
uv venv /tmp/voxeye-testpypi
uv pip install --python /tmp/voxeye-testpypi \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ voxeye
/tmp/voxeye-testpypi/bin/python -c "import voxeye; print(voxeye.__version__)"
```

## 5. Publish to PyPI  *(needs PyPI auth — credential gate)*
**Option A — GitHub Actions (recommended):** add this repo as a trusted publisher on PyPI
for `voxeye`, create a `pypi` GitHub Environment, then **publish a GitHub Release** — the
workflow builds, `twine check`s, and uploads automatically (no tokens).

**Option B — local with a PyPI API token:**
```bash
uvx twine upload dist/*
```

Confirm: `pip install voxeye` works from a clean environment.

---

## Notes
- **Versions are immutable on PyPI** — you can't re-upload `0.1.0`. Use TestPyPI for trial
  runs; bump the version for any real re-publish.
- Trusted publishing is configured **per index** (PyPI and TestPyPI are separate) and per
  GitHub Environment (`pypi` / `testpypi`). No API tokens live in the repo.
- The publish workflow lives in `.github/workflows/publish.yml`.
