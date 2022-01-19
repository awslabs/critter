# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import pytest

# Add '/<repo-root>/critter' to the path
repo_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(repo_root, "critter"))


@pytest.fixture(scope="session", autouse=True)
def env_vars():
    # Mocked AWS credentials to be sure api calls are not accidentally made
    os.environ["AWS_ACCESS_KEY_ID"] = "test-ACCESS_KEY_ID"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test-SECRET_ACCESS_KEY"
    os.environ["AWS_SECURITY_TOKEN"] = "test-SECURITY_TOKEN"
    os.environ["AWS_SESSION_TOKEN"] = "test-SESSION_TOKEN"
    os.environ["AWS_REGION"] = "test-AWS_REGION"


@pytest.fixture()
def test_stacks_cw_loggroup_retention_period():
    path = os.path.join(repo_root, "examples", "test-stacks", "cw-loggroup-retention-period.yml")
    with open(path) as f:
        return f.read()
