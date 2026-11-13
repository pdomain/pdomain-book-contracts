#!/usr/bin/env bash
set -eu

RELEASE_REPO="pdomain/pdomain-book-contracts"
RELEASE_PREFLIGHT="just ci"

. "$(dirname "$0")/release-common.sh"
pdomain_release_main "$@"
