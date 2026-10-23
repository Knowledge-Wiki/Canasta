# AMD64 member of the existing multi-architecture 52b756f6... release.
# This release supports AMD64; pin the member to avoid cross-platform cache ambiguity.
FROM --platform=linux/amd64 ghcr.io/canastawiki/canasta@sha256:e2d3f9ca1441ac3ec8d2aa8e972abc493984af1a4cc16fe2b17c866ec3954e84

# Preserve the deployed Canasta/MW/Composer application layer.
# Upgrade every installed binary package built from the Debian php8.2 source.
ARG PHP_DEBIAN_VERSION=8.2.35-1~deb12u1
RUN /bin/bash <<'BASH'
set -euxo pipefail
    test "$(dpkg --print-architecture)" = amd64; \
    mapfile -t php_packages < <(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package} ${source:Package}\n' | awk '$1 == "ii" && $3 == "php8.2" {print $2}'); \
    test "${#php_packages[@]}" -gt 0; \
    pinned_packages=(); \
    for package in "${php_packages[@]}"; do pinned_packages+=("${package}=${PHP_DEBIAN_VERSION}"); done; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade \
        -o Dpkg::Options::=--force-confold "${pinned_packages[@]}"; \
    for package in "${php_packages[@]}"; do test "$(dpkg-query -W -f='${Version}' "$package")" = "$PHP_DEBIAN_VERSION"; done; \
    php -r 'exit(version_compare(PHP_VERSION, "8.2.35", ">=") && PHP_MAJOR_VERSION === 8 && PHP_MINOR_VERSION === 2 ? 0 : 1);'; \
    php-fpm8.2 -v; \
    rm -rf /var/lib/apt/lists/*
BASH
