# Releasing

This repository publishes to PyPI from `.github/workflows/release.yaml`.
A release happens when you push a Git tag that matches `v*`.

The workflow then:

1. checks that the tag version matches `pyproject.toml`
2. runs `uv run pytest`
3. builds the package with `uv build`
4. checks the distributions with `uvx twine check dist/*`
5. publishes `dist/` to PyPI

## Preferred release flow

Prepare every release in a pull request, even when you can push directly to `main`. This keeps the version bump reviewed and ensures CI passes before the release is tagged.

### 1. Open a release PR

Create a branch from `main`:

```sh
git checkout main
git pull origin main
git checkout -b release/0.1.5
```

Bump the version and verify the release locally:

```sh
uv version 0.1.5
make verify-release
```

Commit the version bump:

```sh
git add pyproject.toml uv.lock
git commit -m "Release 0.1.5"
git push origin release/0.1.5
```

Open a pull request into `main` and merge it.

### 2. Tag the merged commit on `main`

After the PR is merged, update your local `main` and tag that exact commit:

```sh
git checkout main
git pull origin main
make tag-release VERSION=0.1.5
git push origin v0.1.5
```

That tag push starts the release workflow.

You can also set the version with `uv version 0.1.5` instead of using a Make target.

## Direct release flow

Use the direct flow only when a release PR is not practical. If you can push directly to `main`, run:

```sh
make bump-patch          # or bump-minor / bump-major
make verify-release
git add pyproject.toml uv.lock
git commit -m "Release 0.1.5"
make tag-release VERSION=0.1.5
git push origin main
git push origin v0.1.5
```

## Important detail

The tag must include the `v` prefix.

Use:

```sh
git tag v0.1.5
```

Do not use:

```sh
git tag 0.1.5
```

The workflow only listens for `v*` tags.

## PyPI trusted publishing

Publishing uses GitHub OIDC through `pypa/gh-action-pypi-publish`.
The PyPI project must be configured to trust this repository and workflow.

## Available release helpers

```sh
make sync
make test
make lint
make format-check
make build
make check-dist
make verify-release
make bump-patch
make bump-minor
make bump-major
make tag-release VERSION=x.y.z
```
