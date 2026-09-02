#!/usr/bin/env bash
set -eu

RELEASE_REPO="pdomain/pdomain-book-contracts"
# This repo's Makefile has no ci-slow target (unlike pdomain-book-tools);
# make ci already runs lint, typecheck, test, build, and docgraph check.
RELEASE_PREFLIGHT="make ci"

. "$(dirname "$0")/release-common.sh"
pdomain_release_main "$@"
