#!/usr/bin/env bash
# Install and run Redis for local AIDLC / Cache State Engine development.
#
# Usage:
#   ./scripts/redis-local.sh              # ensure installed + running (default)
#   ./scripts/redis-local.sh install      # install only
#   ./scripts/redis-local.sh start        # start
#   ./scripts/redis-local.sh stop         # stop
#   ./scripts/redis-local.sh status       # health + backend
#   ./scripts/redis-local.sh restart      # stop then start
#
# Environment:
#   REDIS_PORT          default 6379
#   REDIS_BACKEND       auto | homebrew | docker  (default: auto)
#   REDIS_DOCKER_NAME   default redis-local
#   REDIS_DOCKER_IMAGE  default redis:alpine
#
# Production: do not use this script. Point REDIS_URL at the centralized
# Redis instance (auth/TLS) and leave local Redis off or on a different port.

set -euo pipefail

PORT="${REDIS_PORT:-6379}"
BACKEND="${REDIS_BACKEND:-auto}"
DOCKER_NAME="${REDIS_DOCKER_NAME:-redis-local}"
DOCKER_IMAGE="${REDIS_DOCKER_IMAGE:-redis:alpine}"
DEFAULT_URL="redis://127.0.0.1:${PORT}/0"

cmd="${1:-ensure}"

log()  { printf '%s\n' "$*"; }
err()  { printf 'error: %s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

redis_ping() {
  if ! have redis-cli; then
    return 1
  fi
  redis-cli -p "${PORT}" ping 2>/dev/null | grep -q PONG
}

detect_backend() {
  if [[ "${BACKEND}" != "auto" ]]; then
    printf '%s\n' "${BACKEND}"
    return
  fi
  if have brew; then
    printf 'homebrew\n'
    return
  fi
  if have docker; then
    printf 'docker\n'
    return
  fi
  printf 'none\n'
}

homebrew_installed() {
  have brew && brew list redis &>/dev/null
}

docker_container_exists() {
  have docker && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "${DOCKER_NAME}"
}

docker_container_running() {
  have docker && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${DOCKER_NAME}"
}

# True if something answers on PORT but is not our known backends.
foreign_listener() {
  if redis_ping; then
    if homebrew_installed && brew services list 2>/dev/null | awk '$1=="redis"{print $2}' | grep -q started; then
      return 1
    fi
    if docker_container_running; then
      return 1
    fi
    # Something else (or unmanaged redis-server) is already serving
    return 0
  fi
  return 1
}

install_homebrew() {
  if ! have brew; then
    err "Homebrew not found. Install from https://brew.sh or set REDIS_BACKEND=docker"
    return 1
  fi
  if homebrew_installed; then
    log "Homebrew redis already installed"
  else
    log "Installing redis via Homebrew..."
    brew install redis
  fi
  if ! have redis-cli; then
    err "redis-cli not on PATH after install; try: brew link redis"
    return 1
  fi
  log "Installed: $(redis-server --version 2>/dev/null || echo redis)"
}

install_docker() {
  if ! have docker; then
    err "Docker not found. Install Docker/Colima or set REDIS_BACKEND=homebrew"
    return 1
  fi
  if ! docker info &>/dev/null; then
    err "Docker daemon is not running"
    return 1
  fi
  log "Pulling ${DOCKER_IMAGE}..."
  docker pull "${DOCKER_IMAGE}"
  log "Docker image ready (${DOCKER_NAME} will be created on start)"
}

do_install() {
  local backend
  backend="$(detect_backend)"
  case "${backend}" in
    homebrew) install_homebrew ;;
    docker)   install_docker ;;
    none)
      err "No supported backend. Install Homebrew (recommended on macOS) or Docker."
      err "  brew install redis   OR   install Docker Desktop / Colima"
      return 1
      ;;
    *)
      err "Unknown REDIS_BACKEND=${backend} (use auto|homebrew|docker)"
      return 1
      ;;
  esac
}

start_homebrew() {
  if ! homebrew_installed; then
    install_homebrew
  fi
  if redis_ping; then
    log "Redis already responding on port ${PORT}"
    return 0
  fi
  log "Starting Redis via Homebrew services..."
  brew services start redis
  # Wait briefly for listen
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if redis_ping; then
      log "Redis is up (homebrew) on port ${PORT}"
      return 0
    fi
    sleep 0.3
  done
  err "Redis did not become ready on port ${PORT}"
  return 1
}

start_docker() {
  if ! have docker || ! docker info &>/dev/null; then
    err "Docker is not available/running"
    return 1
  fi
  if redis_ping && ! docker_container_running; then
    err "Port ${PORT} already in use by a non-docker Redis. Stop it or set REDIS_PORT."
    return 1
  fi
  if docker_container_running; then
    log "Container ${DOCKER_NAME} already running"
    return 0
  fi
  if docker_container_exists; then
    log "Starting existing container ${DOCKER_NAME}..."
    docker start "${DOCKER_NAME}" >/dev/null
  else
    log "Creating container ${DOCKER_NAME} (${DOCKER_IMAGE}) on port ${PORT}..."
    docker run -d \
      --name "${DOCKER_NAME}" \
      -p "${PORT}:6379" \
      --restart unless-stopped \
      "${DOCKER_IMAGE}" >/dev/null
  fi
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if redis_ping; then
      log "Redis is up (docker/${DOCKER_NAME}) on port ${PORT}"
      return 0
    fi
    sleep 0.3
  done
  err "Docker Redis did not become ready on port ${PORT}"
  return 1
}

do_start() {
  local backend
  backend="$(detect_backend)"
  if redis_ping; then
    log "Redis already responding on port ${PORT}"
    log "  REDIS_URL=${DEFAULT_URL}"
    return 0
  fi
  case "${backend}" in
    homebrew) start_homebrew ;;
    docker)   start_docker ;;
    none)
      err "Nothing to start with. Run: $0 install"
      return 1
      ;;
    *)
      err "Unknown REDIS_BACKEND=${backend}"
      return 1
      ;;
  esac
  log "  REDIS_URL=${DEFAULT_URL}"
}

stop_homebrew() {
  if homebrew_installed; then
    log "Stopping Homebrew redis..."
    brew services stop redis || true
  fi
}

stop_docker() {
  if docker_container_running; then
    log "Stopping container ${DOCKER_NAME}..."
    docker stop "${DOCKER_NAME}" >/dev/null
  fi
}

do_stop() {
  local backend
  backend="$(detect_backend)"
  # Prefer stopping whatever we can identify; avoid killing foreign listeners.
  case "${backend}" in
    homebrew)
      stop_homebrew
      ;;
    docker)
      stop_docker
      ;;
    auto|*)
      if docker_container_running; then
        stop_docker
      elif homebrew_installed; then
        stop_homebrew
      else
        err "Could not identify a managed Redis to stop"
        return 1
      fi
      ;;
  esac
  if redis_ping; then
    err "Something is still answering on port ${PORT} (foreign process?)"
    return 1
  fi
  log "Redis stopped (port ${PORT} clear)"
}

do_status() {
  local backend ping_ok="no" method="unknown"
  backend="$(detect_backend)"

  if redis_ping; then
    ping_ok="yes"
  fi

  if docker_container_running; then
    method="docker (${DOCKER_NAME})"
  elif homebrew_installed && brew services list 2>/dev/null | awk '$1=="redis"{print $2}' | grep -q started; then
    method="homebrew services"
  elif redis_ping; then
    method="external (port ${PORT} answers; not managed by this script)"
  else
    method="none"
  fi

  log "Redis local status"
  log "  port:     ${PORT}"
  log "  backend:  ${backend}"
  log "  method:   ${method}"
  log "  ping:     ${ping_ok}"
  log "  REDIS_URL=${REDIS_URL:-$DEFAULT_URL}"
  if [[ "${ping_ok}" == "yes" ]] && have redis-cli; then
    log "  version:  $(redis-cli -p "${PORT}" INFO server 2>/dev/null | awk -F: '/^redis_version/{print $2}' | tr -d '\r')"
    log "  dbsize:   $(redis-cli -p "${PORT}" DBSIZE 2>/dev/null | tr -d '\r')"
  fi
  if [[ "${ping_ok}" != "yes" ]]; then
    return 1
  fi
}

do_ensure() {
  local backend
  backend="$(detect_backend)"
  if [[ "${backend}" == "none" ]]; then
    err "No Homebrew or Docker available to install Redis"
    return 1
  fi
  if ! redis_ping; then
    # Install if backend bits missing
    case "${backend}" in
      homebrew)
        if ! homebrew_installed; then
          do_install
        fi
        ;;
      docker)
        if ! have docker; then
          do_install
        fi
        ;;
    esac
    do_start
  else
    log "Redis already up on port ${PORT}"
    log "  REDIS_URL=${DEFAULT_URL}"
  fi
  do_status || true
  log ""
  log "Next:"
  log "  export REDIS_URL=${DEFAULT_URL}"
  log "  cd cache-ui && ./run.sh    # Cache State Engine → http://127.0.0.1:8787"
  log ""
  log "Prod: set REDIS_URL to the centralized instance (do not use this script)."
}

do_restart() {
  do_stop || true
  do_start
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [ensure|install|start|stop|status|restart]

Local Redis for AIDLC Cache State Engine development.

  ensure   Install if needed and start (default)
  install  Install Redis (Homebrew preferred, else Docker)
  start    Start Redis
  stop     Stop managed Redis
  status   Show ping / backend
  restart  Stop then start

Env: REDIS_PORT REDIS_BACKEND=auto|homebrew|docker REDIS_DOCKER_NAME REDIS_DOCKER_IMAGE

Prod: export REDIS_URL=rediss://:TOKEN@your-central-host:6379/0
EOF
}

case "${cmd}" in
  ensure|up)   do_ensure ;;
  install)     do_install ;;
  start)       do_start ;;
  stop)        do_stop ;;
  status)      do_status ;;
  restart)     do_restart ;;
  -h|--help|help) usage ;;
  *)
    err "Unknown command: ${cmd}"
    usage
    exit 2
    ;;
esac
