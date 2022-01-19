# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import patch, MagicMock, call

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
resources = {
    "compliant-one": {"evaluation_result": {}, "expected_compliance_type": "COMPLIANT"},
    "compliant-two": {"evaluation_result": {}, "expected_compliance_type": "COMPLIANT"},
    "non-compliant-one": {"evaluation_result": {}, "expected_compliance_type": "NON_COMPLIANT"},
    "non-compliant-two": {"evaluation_result": {}, "expected_compliance_type": "NON_COMPLIANT"},
    "not-applicable-one": {"evaluation_result": {}, "expected_compliance_type": "NOT_APPLICABLE"},
}


@patch("time.sleep")
@patch("boto3.resource")
@patch("boto3.client")
def test_stack_wait_for_config_resources(mock_boto_client, mock_boto_resource, mock_time_sleep, caplog):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.skip_wait_for_resource_recording = False
    stack.resource_types = rule["Scope"]["ComplianceResourceTypes"]
    stack.config_rule_name = rule["ConfigRuleName"]
    stack.resources = resources
    stack.config = MagicMock()
    # TODO: test a loop, return less than all of the resources on the first
    # config.batch_get_resource_config api call, then return all resources on the second call
    stack.config.batch_get_resource_config.return_value = {"baseConfigurationItems": resources.keys()}

    stack.wait_for_config_resources()

    assert mock_boto_client.call_args_list == [call("sts"), call("cloudformation"), call("config")]
    assert mock_boto_resource.call_args_list == []
    assert mock_time_sleep.call_args_list == []
    assert stack.config.batch_get_resource_config.call_args_list == [
        call(
            resourceKeys=[
                {"resourceType": "AWS::Logs::LogGroup", "resourceId": "compliant-one"},
                {"resourceType": "AWS::Logs::LogGroup", "resourceId": "compliant-two"},
                {"resourceType": "AWS::Logs::LogGroup", "resourceId": "non-compliant-one"},
                {"resourceType": "AWS::Logs::LogGroup", "resourceId": "non-compliant-two"},
                {"resourceType": "AWS::Logs::LogGroup", "resourceId": "not-applicable-one"},
            ]
        )
    ]


@patch("boto3.resource")
@patch("boto3.client")
def test_stack_wait_for_config_resources_skip_wait(mock_boto_client, mock_boto_resource):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.skip_wait_for_resource_recording = True
    stack.wait_for_config_resources()
    assert mock_boto_client.call_args_list == [call("sts"), call("cloudformation"), call("config")]
    assert mock_boto_resource.call_args_list == []


@patch("boto3.resource")
@patch("boto3.client")
def test_stack_wait_for_config_resources_not_resource_types(mock_boto_client, mock_boto_resource, caplog):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.skip_wait_for_resource_recording = False
    stack.resource_types = []
    stack.config_rule_name = "test-rule"
    stack.wait_for_config_resources()
    assert mock_boto_client.call_args_list == [call("sts"), call("cloudformation"), call("config")]
    assert mock_boto_resource.call_args_list == []
    assert (
        "Warning - Skipping waiting for resources to be recorded by AWS Config. Config rule "
        "'test-rule' scope does not specify applicable resource types." in caplog.text
    )
