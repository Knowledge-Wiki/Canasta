#!/bin/bash
set -euo pipefail
php /opt/canasta-runtime/verify-composer.php
# Mounted extensions can change class locations without changing dependencies.
# Rebuild their class map using the parent image's existing locked libraries.
COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_DISABLE_NETWORK=1 \
  composer --working-dir="$MW_HOME" dump-autoload \
    --no-dev --no-interaction --no-scripts --optimize
php /opt/canasta-runtime/verify-composer.php
