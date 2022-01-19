# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import patch, mock_open

from critter import Stack


@patch("boto3.client")
@patch("builtins.open", mock_open(read_data="file contents"))
def test_cli(mock_boto_client):
    stack1 = Stack()
    stack1.parse_args(
        [
            "./template1.yml",
            "--trigger-rule-evaluation",
            "--stack-tags",
            '[{"Key": "TagKey1", "Value": "TagValue1"}, {"Key": "TagKey2", "Value": "TagValue2"}]',
        ]
    )
    assert stack1.template_file == "./template1.yml"
    assert stack1.template_body == "file contents"
    assert stack1.stack_name == "Critter-template1"
    assert stack1.delete_stack == "OnSuccess"
    assert stack1.stack_tags == [{"Key": "TagKey1", "Value": "TagValue1"}, {"Key": "TagKey2", "Value": "TagValue2"}]
    assert stack1.cfn_capabilities == []
    assert stack1.trigger_rule_evaluation is True

    stack2 = Stack()
    stack2.parse_args(
        [
            "./template2.yml",
            "--capabilities",
            "CAPABILITY_IAM",
            "--delete-stack",
            "Never",
            "--stack-name",
            "CustomStackName",
        ]
    )
    assert stack2.template_file == "./template2.yml"
    assert stack2.template_body == "file contents"
    assert stack2.stack_name == "CustomStackName"
    assert stack2.delete_stack == "Never"
    assert stack2.stack_tags == [{"Key": "ConfigRuleTesting", "Value": "True"}, {"Key": "Critter", "Value": "True"}]
    assert stack2.cfn_capabilities == ["CAPABILITY_IAM"]
    assert stack2.trigger_rule_evaluation is False
