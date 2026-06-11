# Ownership transfer runbook

What a **new owner** must change when the GitHub repo and/or the PyPI package change hands.
Two things can move independently — the **GitHub repo** (`nilayguptaforwork-ctrl/voxeye`) and
the **PyPI project** (`voxeye`) — so the scenarios below are separable. Do the matching
sections.

> ⚠️ **The #1 thing people forget:** PyPI **Trusted Publishing** is bound to a specific
> GitHub *owner/repo/workflow/environment*. If the GitHub side moves (transfer or rename),
> the old trusted-publisher entry no longer matches and **automated releases silently stop
> working** until you re-register it (see "Trusted Publishing" below).

---

## What is tied to the current owner

| Location | What | Change when… |
|---|---|---|
| `pyproject.toml` → `[project.urls]` (5 lines) | `github.com/nilayguptaforwork-ctrl/voxeye` | GitHub repo moves |
| `pyproject.toml` → `authors` | `Manvendra Singh` | the human author/maintainer changes |
| git remote `origin` | `…/nilayguptaforwork-ctrl/voxeye.git` | GitHub repo moves |
| PyPI project → Collaborators | who has Owner role on `voxeye` | PyPI ownership moves |
| PyPI project → Publishing (Trusted Publisher) | owner/repo/workflow/environment | GitHub repo moves |
| GitHub repo → Settings → Environments | `pypi` (+ `testpypi` if added) | repo is recreated (not transferred) |
| `PUBLISHING.md` | references the publisher fields | GitHub repo moves |

The **import name `voxeye`**, the **PyPI distribution name `voxeye`**, the SDK code, the
LICENSE (Apache-2.0, no embedded name), and the architecture do **not** change on a transfer.

---

## Scenario A — GitHub repo changes hands

Whether you *transfer* the repo (GitHub Settings → Transfer) or recreate it under a new
owner/org `NEWOWNER`:

1. **Remote:** `git remote set-url origin https://github.com/NEWOWNER/voxeye.git`
2. **Edit `pyproject.toml`:** replace `nilayguptaforwork-ctrl` → `NEWOWNER` in the 5
   `[project.urls]`; update `authors` if the person changed.
   ```bash
   sed -i '' 's|nilayguptaforwork-ctrl/voxeye|NEWOWNER/voxeye|g' pyproject.toml PUBLISHING.md OWNERSHIP.md
   ```
3. **GitHub Environments:** if you *recreated* the repo, re-create the `pypi` environment
   (Settings → Environments → New). A true *transfer* keeps environments + history.
4. **Re-register the PyPI Trusted Publisher** — mandatory (see below).
5. **Commit identity going forward:** `git config user.name "NEWOWNER"` (and decide on an
   email or keep `<>`). Existing history keeps the old author unless you rewrite it (rarely
   worth it).
6. Bump the version + release once to confirm the new pipeline publishes (see `PUBLISHING.md`).

> Note: GitHub sets up redirects after a transfer/rename, but OIDC Trusted Publishing uses
> the **new** owner/repo in its token, so step 4 is required regardless of redirects.

## Scenario B — PyPI package changes hands

PyPI has no one-click transfer; you move it via collaborator roles:

1. **Current Owner** → https://pypi.org/manage/project/voxeye/collaboration/ → invite the
   new account with the **Owner** role.
2. **New owner** accepts the invite (needs a PyPI account with **2FA** enabled).
3. Once the new owner confirms access, the previous owner can **remove themselves** (or stay
   as a second Owner).
4. **API tokens:** revoke any old project-scoped tokens (Account → API tokens). The new
   owner mints their own only if they publish with tokens instead of Trusted Publishing.
5. **Review the Trusted Publisher** on the project (Manage → Publishing): it must point at
   whatever GitHub owner/repo will cut releases. If the repo also moved, redo it per below.

## Scenario C — full handoff (both move)

Do **A** then **B**. The order that avoids a broken window: transfer/recreate the GitHub
repo and update its files first, add the new PyPI Owner, then re-register the Trusted
Publisher with the new GitHub coordinates, then verify with a release.

---

## Trusted Publishing — re-registration (the critical step)

On the PyPI project: **Manage → Publishing**. Remove the stale publisher and **add a new
one** with the new coordinates:

| Field | Value |
|---|---|
| PyPI Project Name | `voxeye` |
| Owner | `NEWOWNER` |
| Repository name | `voxeye` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Every field must match the OIDC token the GitHub Action presents, or PyPI rejects the
upload. (Repeat on **TestPyPI** with environment `testpypi` if you use the dry-run path.)
Only a PyPI **Owner** can manage publishers — so on a full handoff, the new owner does this
*after* accepting the Owner role in Scenario B.

---

## Verify the handoff
```bash
# 1. metadata points at the new owner
grep github.com pyproject.toml

# 2. a release publishes end-to-end (bump version first — see PUBLISHING.md)
gh release create vX.Y.Z --title "voxeye X.Y.Z" --notes "…"

# 3. it lands on PyPI under the new ownership
uv venv /tmp/v && uv pip install --python /tmp/v voxeye==X.Y.Z
```

If the release workflow fails at the upload step with an OIDC/authorization error, the
Trusted Publisher coordinates don't match the new repo — recheck the table above.
