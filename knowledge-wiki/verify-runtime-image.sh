#!/usr/bin/env bash
# Offline checks of the actual AMD64 image; no cluster or host mounts are used.
set -euo pipefail
IMAGE="${1:?Usage: verify-runtime-image.sh <image>}"
EXPECTED_PHP_VERSION="${2:-8.2.35}"
docker run --rm -i --platform linux/amd64 --network none \
  --env "EXPECTED_PHP_VERSION=$EXPECTED_PHP_VERSION" \
  --entrypoint bash "$IMAGE" -s <<'BASH'
set -euo pipefail
test "$(dpkg --print-architecture)" = amd64
php -r 'exit(PHP_VERSION === getenv("EXPECTED_PHP_VERSION") ? 0 : 1);'
php -v
php-fpm8.2 -v
php-fpm8.2 -t
apachectl -t
composer --working-dir="$MW_HOME" check-platform-reqs --no-dev
test ! -e /opt/canasta-runtime
mkdir -p /run/php
cat > /var/www/mediawiki/canasta-php-check.php <<'PHP'
<?php
header('Content-Type: application/json');
echo json_encode(['version' => PHP_VERSION, 'sapi' => PHP_SAPI]);
PHP
php-fpm8.2 -D
apachectl start
trap 'apachectl stop >/dev/null 2>&1 || true' EXIT
for attempt in {1..30}; do
  if curl --fail --silent http://127.0.0.1/canasta-php-check.php > /tmp/canasta-http.json; then
    php -r '$d = json_decode(file_get_contents("/tmp/canasta-http.json"), true); exit($d["version"] === getenv("EXPECTED_PHP_VERSION") && $d["sapi"] === "fpm-fcgi" ? 0 : 1);'
    printf 'PASS Apache serves requests through patched PHP-FPM\n'
    exit 0
  fi
  sleep 0.2
done
echo 'Patched web runtime did not start' >&2
exit 1
BASH
