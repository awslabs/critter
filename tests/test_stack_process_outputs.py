# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import patch, MagicMock, call
import pytest

from critter import Stack


rule = {
    "ConfigRuleName": "my-config-rule",
    "ConfigRuleArn": "arn:aws:config:us-region-1:111111111111:config-rule/config-rule-aaa111",
    "ConfigRuleId": "config-rule-aaa111",
    "Description": "CloudWatch LogGroup retention period rule",
    "Scope": {"ComplianceResourceTypes": ["AWS::Logs::LogGroup"]},
    "Source": {"Owner": "AWS", "SourceIdentifier": "CW_LOGGROUP_RETENTION_PERIOD_CHECK"},
    "MaximumExecutionFrequency": "TwentyFour_Hours",
    "ConfigRuleState": "ACTIVE",
}


@patch("time.sleep")
@patch("boto3.resource")
@patch("boto3.client")
def test_stack_process_outputs(mock_boto_client, mock_boto_resource, mock_time_sleep, caplog):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.stack = MagicMock()
    stack.stack.outputs = [
        {"OutputKey": "MyCustomKey", "OutputValue": "MyCustomValue"},
        {"OutputKey": "ConfigRuleName", "OutputValue": "my-config-rule"},
        {"OutputKey": "CompliantResourceIds", "OutputValue": "compliant-one,compliant-two"},
        {"OutputKey": "NonCompliantResourceIds", "OutputValue": "non-compliant-one, non-compliant-two"},
        {"OutputKey": "NotApplicableResourceIds", "OutputValue": "not-applicable-one"},
        {"OutputKey": "DelayAfterDeploy", "OutputValue": "5"},
    ]
    stack.deploy_action_performed = "UPDATE"

    stack.config = MagicMock()
    stack.config.describe_config_rules.return_value = {"ConfigRules": [rule]}

    stack.process_outputs()

    assert mock_boto_client.call_args_list == [call("sts"), call("cloudformation"), call("config")]
    assert mock_boto_resource.call_args_list == []

    assert stack.stack_outputs == {
        "CompliantResourceIds": "compliant-one,compliant-two",
        "ConfigRuleName": "my-config-rule",
        "DelayAfterDeploy": "5",
        "MyCustomKey": "MyCustomValue",
        "NonCompliantResourceIds": "non-compliant-one, non-compliant-two",
        "NotApplicableResourceIds": "not-applicable-one",
        "SkipWaitForResourceRecording": "False",
    }
    assert stack.delay_after_deploy == 5
    assert mock_time_sleep.call_args_list == [call(5)]
    assert stack.config_rule_name == "my-config-rule"
    assert stack.config_rule == rule
    assert stack.resources == {
        "compliant-one": {"evaluation_result": {}, "expected_compliance_type": "COMPLIANT"},
        "compliant-two": {"evaluation_result": {}, "expected_compliance_type": "COMPLIANT"},
        "non-compliant-one": {"evaluation_result": {}, "expected_compliance_type": "NON_COMPLIANT"},
        "non-compliant-two": {"evaluation_result": {}, "expected_compliance_type": "NON_COMPLIANT"},
        "not-applicable-one": {"evaluation_result": {}, "expected_compliance_type": "NOT_APPLICABLE"},
    }
    assert stack.skip_wait_for_resource_recording is False
    assert (
        "Warning - Testing for NOT_APPLICABLE compliance type is experimental and may yield unexpected results."
        in caplog.text
    )


@patch("boto3.resource")
@patch("boto3.client")
def test_stack_process_outputs_config_rule_name_missing(mock_boto_client, mock_boto_resource):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.stack = MagicMock()
    stack.stack.outputs = []
    stack.stack_name = "MyStack"

    with pytest.raises(Exception, match="Missing required output 'ConfigRuleName' on CloudFormation stack 'MyStack'"):
        stack.process_outputs()


@patch("boto3.resource")
@patch("boto3.client")
def test_stack_process_outputs_resource_ids_missing(mock_boto_client, mock_boto_resource):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.stack = MagicMock()
    stack.stack.outputs = [
        {"OutputKey": "ConfigRuleName", "OutputValue": "my-config-rule"},
    ]

    stack.config = MagicMock()
    stack.config.describe_config_rules.return_value = {"ConfigRules": [rule]}

    exc_match = "Error - Did not find any resource ids outputs. Specify one or more of the following CloudFormation "
    "stack outputs: ['CompliantResourceIds', 'NonCompliantResourceIds', 'NotApplicableResourceIds']"
    with pytest.raises(Exception, match=exc_match):
        stack.process_outputs()
