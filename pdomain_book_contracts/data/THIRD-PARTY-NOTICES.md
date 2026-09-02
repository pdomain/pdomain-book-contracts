# Third-party notices for vendored data

This directory contains non-code data files vendored from third-party
projects. They are redistributed with `pdomain_book_contracts` under the
terms described below. The `pdomain_book_contracts` repository `LICENSE`
covers only the project's own source code and does **not** relicense this
vendored data.

## `spdx_licenses.json`

- **Upstream project:** SPDX `license-list-data`
- **Repository:** <https://github.com/spdx/license-list-data>
- **Description:** Machine-readable form of the SPDX License List. Only the
  `licenseId` field of each entry is retained; all other fields are dropped
  to keep the vendored file small.
- **License:** CC0-1.0 (Creative Commons Zero v1.0 Universal). The SPDX
  License List data is published into the public domain by the SPDX project.
  See <https://spdx.org/licenses/> and the upstream repository for details.
- **Vendored:** 2026-05-22. Refresh by re-extracting the `licenseId` values
  from the upstream `json/licenses.json` file.
