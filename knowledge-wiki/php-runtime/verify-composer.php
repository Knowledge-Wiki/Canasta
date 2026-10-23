<?php
// Refuse unreviewed dependency changes before serving requests or running jobs.
$home = getenv('MW_HOME');
$manifest = json_decode(file_get_contents(__DIR__ . '/composer-inputs.json'), true, 512, JSON_THROW_ON_ERROR);
foreach ($manifest as $relative => $allowedHashes) {
    $path = $home . '/' . $relative;
    if (!is_file($path) || !in_array(hash_file('sha256', $path), $allowedHashes, true)) {
        fwrite(STDERR, "Canasta dependency input changed: $relative. Build and test a new runtime image.\n");
        exit(1);
    }
}
$mounted = getenv('MW_VOLUME') . '/config/composer.local.json';
if (is_file($mounted) && !in_array(hash_file('sha256', $mounted), $manifest['composer.local.json'], true)) {
    fwrite(STDERR, "Canasta mounted Composer configuration differs from the tested image.\n");
    exit(1);
}
