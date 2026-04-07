#!/bin/bash
# Rapidly — wait for MinIO to become available, then run the setup script.

export CMD_MC=$(which mc)

echo "[rapidly] Waiting for MinIO to accept connections..."
until ($CMD_MC config host add rapidly http://$MINIO_HOST:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD)
do
  sleep 1;
done;
echo "[rapidly] MinIO is ready."

bash $1
