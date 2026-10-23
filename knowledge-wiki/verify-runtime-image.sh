#!/usr/bin/env bash
# Offline checks of the actual AMD64 image; no cluster or host mounts are used.
set -euo pipefail
IMAGE="${1:?Usage: verify-runtime-image.sh <image>}"
docker run --rm -i --platform linux/amd64 --network none \
  --entrypoint bash "$IMAGE" -s <<'BASH'
set -euo pipefail
test "$(dpkg --print-architecture)" = amd64
php -r 'exit(PHP_MAJOR_VERSION === 8 && PHP_MINOR_VERSION === 2 && version_compare(PHP_VERSION, "8.2.35", ">=") ? 0 : 1);'
php -v
php-fpm8.2 -v
php-fpm8.2 -t
apachectl -t
mkdir -p "$MW_HOME/user-extensions" "$MW_HOME/user-skins" "$MW_VOLUME/config"
/create-symlinks.sh
lock_before=$(sha256sum "$MW_HOME/composer.lock")
packages_before=$(sha256sum "$MW_HOME/vendor/composer/installed.json")
/opt/canasta-runtime/prepare-composer.sh
test "$lock_before" = "$(sha256sum "$MW_HOME/composer.lock")"
test "$packages_before" = "$(sha256sum "$MW_HOME/vendor/composer/installed.json")"
composer --working-dir="$MW_HOME" check-platform-reqs --no-dev
printf 'PASS offline autoload preparation preserves locked package versions\n'

# A changed mounted merge configuration must fail before application startup.
printf '{"require":{"unexpected/package":"*"}}\n' > "$MW_VOLUME/config/composer.local.json"
if php /opt/canasta-runtime/verify-composer.php > /tmp/guard.log 2>&1; then
  echo 'Dependency drift was incorrectly accepted' >&2
  exit 1
fi
grep -q 'mounted Composer configuration differs' /tmp/guard.log
rm "$MW_VOLUME/config/composer.local.json"
printf 'PASS unreviewed mounted dependencies are rejected\n'

# Changing an extension dependency manifest must also fail.
cp "$MW_HOME/extensions/OpenIDConnect/composer.json" /tmp/oidc-composer.json
printf '\n' >> "$MW_HOME/extensions/OpenIDConnect/composer.json"
if php /opt/canasta-runtime/verify-composer.php > /tmp/guard.log 2>&1; then
  echo 'Extension dependency drift was incorrectly accepted' >&2
  exit 1
fi
grep -q 'OpenIDConnect/composer.json' /tmp/guard.log
cp /tmp/oidc-composer.json "$MW_HOME/extensions/OpenIDConnect/composer.json"
php /opt/canasta-runtime/verify-composer.php
printf 'PASS unreviewed extension dependencies are rejected\n'

test "$MW_AUTOUPDATE" = false
test "$MW_ENABLE_JOB_RUNNER" = false
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
    php -r '$d = json_decode(file_get_contents("/tmp/canasta-http.json"), true); exit(version_compare($d["version"], "8.2.35", ">=") && $d["sapi"] === "fpm-fcgi" ? 0 : 1);'
    printf 'PASS Apache serves requests through patched PHP-FPM\n'
    exit 0
  fi
  sleep 0.2
done
echo 'Patched web runtime did not start' >&2
exit 1
BASH
