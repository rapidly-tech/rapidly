#!/bin/bash
# Rapidly — download the MinIO client and run the local bucket configuration
# used by the Rapidly development environment.

wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc

export CMD_MC=./mc
bash ./configure.sh
