#!/bin/sh
# Single-instance service: apply migrations on start, then hand over to CMD.
set -eu
cookbook migrate
exec "$@"
