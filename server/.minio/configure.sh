#!/bin/bash
# Rapidly — configure MinIO buckets, access policies, and credentials.

$CMD_MC alias set rapidly http://$MINIO_HOST:${MINIO_PORT:-9000} $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD;

# ── IAM user & access policy ──────────────────────────────────────
$CMD_MC admin user add rapidly $ACCESS_KEY $SECRET_ACCESS_KEY
$CMD_MC admin policy create rapidly rapidly-development $POLICY_FILE
$CMD_MC admin policy attach rapidly rapidly-development --user $ACCESS_KEY

# ── Storage buckets ───────────────────────────────────────────────
# Private bucket — uploaded files (versioned for rollback support)
$CMD_MC mb rapidly/$BUCKET_NAME --with-versioning --ignore-existing

# Public bucket — publicly downloadable assets
$CMD_MC mb rapidly/$PUBLIC_BUCKET_NAME --with-versioning --ignore-existing
$CMD_MC anonymous set download rapidly/$PUBLIC_BUCKET_NAME

# Testing bucket — isolated storage for the test suite
$CMD_MC mb rapidly/$BUCKET_TESTING_NAME --with-versioning --ignore-existing
