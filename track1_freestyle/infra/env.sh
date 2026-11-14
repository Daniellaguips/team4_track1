# Local-runtime shim for hosts where the Docker daemon socket is not accessible to the user:
# rootless Podman with storage on local tmpfs, exposed through a user-level API socket.
# Not needed on a host with a working Docker daemon (omit `-e podman` there).
T1_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CONTAINERS_STORAGE_CONF="$T1_ROOT/infra/storage.conf"
export CONTAINERS_REGISTRIES_CONF="$T1_ROOT/infra/registries.conf"
export T1_PODMAN_SOCK="${T1_PODMAN_SOCK:-/tmp/yt35_t1/podman.sock}"
export DOCKER_HOST="unix://$T1_PODMAN_SOCK"
export PATH="$T1_ROOT/infra/bin:$T1_ROOT/.venv/bin:$PATH"
mkdir -p /tmp/yt35_t1/containers/graph /tmp/yt35_t1/containers/run
if ! [ -S "$T1_PODMAN_SOCK" ] || ! docker version >/dev/null 2>&1; then
  pkill -f "podman system service --time=0 unix://$T1_PODMAN_SOCK" 2>/dev/null || true
  nohup podman system service --time=0 "unix://$T1_PODMAN_SOCK" >/tmp/yt35_t1/podman_service.log 2>&1 &
  sleep 2
fi
