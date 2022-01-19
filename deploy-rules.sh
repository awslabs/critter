#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

set -ex

# Ensure arg 1 is a file that exists
export S3_BUCKET="$1"
if [ -z "$S3_BUCKET" ]; then
  echo "Error - Specify S3 bucket name for CloudFormation template upload"
  echo "Usage: $0 <s3-bucket-name>"
  exit 1
fi

set -u

export SCRIPT_DIR="$(dirname "$0")"

export TEMPLATES_DIR="${SCRIPT_DIR}/examples/config-rules"
export PACKAGED_DIR="${TEMPLATES_DIR}/packaged"

rm -rf "$PACKAGED_DIR"
mkdir -p "$PACKAGED_DIR"

function deploy-template {
  # Ensure arg 1 is a file that exists
  local TEMPLATE="$1"
  if [ ! -f "$TEMPLATE" ]; then
    echo "WARN - File '$1' does not exist to deploy!"
    echo "Usage: $0 TEMPLATE"
    exit 1
  fi

  local FILENAME="$(basename "$TEMPLATE")"
  local STACK_NAME="ConfigRule-${FILENAME%.*}"

  aws cloudformation package \
    --template-file "$TEMPLATE" \
    --s3-bucket "$S3_BUCKET" \
    --output-template-file "${PACKAGED_DIR}/${FILENAME}" &&
  aws cloudformation deploy \
    --template-file "${PACKAGED_DIR}/${FILENAME}" \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_IAM
}

echo "Deploying Config rule templates"

for TEMPLATE in $(find "$TEMPLATES_DIR" -type f -name '*.y*ml'); do
  deploy-template "$TEMPLATE"
done
