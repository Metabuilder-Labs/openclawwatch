# 12 — Publish Workflows

GitHub Actions workflows for publishing releases to PyPI and npm.

## publish-pypi.yml

- **Trigger:** `on: release: types: [published]`, only if tag starts with `v`
- **Job:** `publish-pypi`, `ubuntu-latest`
- **Permissions:** `id-token: write` for PyPI trusted publishing
- **Environment:** `pypi`
- **Steps:** checkout → setup Python 3.12 → install build → run test suite → `python -m build` → `pypa/gh-action-pypi-publish@release/v1` (no API token — trusted publishing)
- Tests must pass before publishing; if they fail, the publish step is skipped

## publish-npm.yml

- **Trigger:** `on: release: types: [published]`, only if tag starts with `v`
- **Job:** `publish-npm`, `ubuntu-latest`
- **Steps:** checkout → setup Node 20 (registry-url: `https://registry.npmjs.org`) → `cd sdk-ts` → `npm install` → `npm test` → `npm run build` → `npm publish --access public`
- Uses `NPM_TOKEN` secret as `NODE_AUTH_TOKEN` env var
- Tests must pass before publishing; if they fail, the publish step is skipped

## Package name change

`sdk-ts/package.json` name changed from `@openclawwatch/sdk` to `@openclawwatch/sdk`.
