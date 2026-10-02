# Shared helpers for the operations scripts (sourced, not executed).
# Postgres client tools come from a container, so the host needs only Docker.
PG_TOOLS_IMAGE="${PG_TOOLS_IMAGE:-postgres:17-alpine}"   # v17 clients read PG 15–17 servers

compose() { docker compose ${COMPOSE_FILES:-} "$@"; }

# Run a client tool (pg_dump, pg_restore, psql) against a URL reachable from the host.
pg_client() {
  docker run --rm -i --network host -v "$PWD:/work" -w /work "$PG_TOOLS_IMAGE" "$@"
}

# Run a client tool inside the Compose network against the local `db` service.
pg_local() {
  compose exec -T db "$@"
}

die() { echo "ERROR: $*" >&2; exit 1; }

# Run a v17 client tool on the Compose network against the `db` service
# (newer clients read archives written by newer pg_dump versions).
pg_net() {
  local cid net pw
  cid="$(compose ps -q db)"; [ -n "$cid" ] || die "the db service is not running"
  net="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$cid" | awk '{print $1}')"
  pw="$(compose exec -T db printenv POSTGRES_PASSWORD)"
  docker run --rm -i --network "$net" -e PGPASSWORD="$pw" -e PGHOST=db \
    ${PG_NET_MOUNT:+-v "$PG_NET_MOUNT:/in:ro"} \
    -e PGUSER="${POSTGRES_USER:-proptech}" -e PGDATABASE="${POSTGRES_DB:-proptech}" \
    "$PG_TOOLS_IMAGE" "$@"
}
