#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

set -eux

TEMPLATES_DIR="${CODEBUILD_SRC_DIR}/config-rules"
PACKAGED_DIR="${TEMPLATES_DIR}/packaged"

rm -rf "$PACKAGED_DIR"
mkdir -p "$PACKAGED_DIR"

STACK_NAME_PREFIX="$(echo "$CODEBUILD_BUILD_ID" | cut -d ':' -f 1)"

for TEMPLATE in $(find "$TEMPLATES_DIR" -type f -name '*.y*ml'); do
  FILENAME="$(basename "$TEMPLATE")"
  STACK_NAME="${STACK_NAME_PREFIX}-${FILENAME%.*}"

  aws cloudformation package \
    --template-file "$TEMPLATE" \
    --s3-bucket "$CFN_PACKAGE_S3_BUCKET" \
    --output-template-file "${PACKAGED_DIR}/${FILENAME}"

  aws cloudformation deploy \
    --template-file "${PACKAGED_DIR}/${FILENAME}" \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_IAM \
    --no-fail-on-empty-changeset
done
