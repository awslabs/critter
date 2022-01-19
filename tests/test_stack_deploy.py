# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError

from critter import Stack


@patch("boto3.resource")
@patch("boto3.client")
def test_stack_deploy_create(mock_boto_client, mock_boto_resource, test_stacks_cw_loggroup_retention_period):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.template_file = "./template.yml"
    stack.stack_name = "TestStack"
    stack.template_body = test_stacks_cw_loggroup_retention_period
    stack.cfn_capabilities = []
    stack.stack_tags = [{"Key": "TagKey", "Value": "TagValue"}]

    stack.cfn = MagicMock()
    stack_resource = MagicMock()
    mock_boto_resource.return_value.Stack.return_value = stack_resource

    stack.deploy()

    assert mock_boto_client.call_args_list == [call("sts"), call("cloudformation"), call("config")]
    assert mock_boto_resource.call_args_list == [call("cloudformation")]
    assert mock_boto_resource.return_value.Stack.call_args_list == [call("TestStack")]
    assert stack.stack == stack_resource
    assert stack.cfn.create_stack.call_args_list == [
        call(
            StackName="TestStack",
            TemplateBody=test_stacks_cw_loggroup_retention_period,
            OnFailure="DELETE",
            Capabilities=[],
            Tags=[{"Key": "TagKey", "Value": "TagValue"}],
        )
    ]
    assert stack.cfn.get_waiter.call_args_list == [call("stack_create_complete")]
    assert stack.deploy_action_performed == "CREATE"


@patch("boto3.resource")
@patch("boto3.client")
def test_stack_deploy_update(mock_boto_client, mock_boto_resource, test_stacks_cw_loggroup_retention_period, caplog):
    stack = Stack()
    stack.initialize_boto_clients()
    stack.template_file = "./template.yml"
    stack.stack_name = "TestStack"
    stack.template_body = test_stacks_cw_loggroup_retention_period
    stack.cfn_capabilities = ["CAPABILITY_IAM"]
    stack.stack_tags = [{"Key": "TagKey", "Value": "TagValue"}]
    stack.trigger_rule_evaluation = False

    stack.cfn = MagicMock()
    stack.cfn.create_stack.side_effect = ClientError({"Error": {"Code": "AlreadyExistsException"}}, "CreateStack")
    stack_resource = MagicMock()
    mock_boto_resource.return_value.Stack.return_value = stack_resource

    stack.deploy()

    assert mock_boto_client.call_args_list == [call("sts"), call("cloudformation"), call("config")]
    assert mock_boto_resource.call_args_list == [call("cloudformation")]
    assert mock_boto_resource.return_value.Stack.call_args_list == [call("TestStack")]
    assert stack.stack == stack_resource
    assert stack.cfn.create_stack.call_args_list == [
        call(
            StackName="TestStack",
            TemplateBody=test_stacks_cw_loggroup_retention_period,
            OnFailure="DELETE",
            Capabilities=["CAPABILITY_IAM"],
            Tags=[{"Key": "TagKey", "Value": "TagValue"}],
        )
    ]
    assert stack.cfn.update_stack.call_args_list == [
        call(
            StackName="TestStack",
            TemplateBody=test_stacks_cw_loggroup_retention_period,
            DisableRollback=True,
            Capabilities=["CAPABILITY_IAM"],
            Tags=[{"Key": "TagKey", "Value": "TagValue"}],
        )
    ]
    assert stack.cfn.get_waiter.call_args_list == [call("stack_update_complete")]
    assert stack.deploy_action_performed == "UPDATE"
    assert (
        "Warning - Updating existing CloudFormation stack 'TestStack'. Testing using existing stacks may "
        "result in unreliable test results. It is recommended to deploy a new stack for each test iteration."
        in caplog.text
    )
    assert (
        "Warning - Updating an existing CloudFormation stack without specifying '--trigger-rule-evaluation' may "
        "result in the Config rule evaluation never occurring." in caplog.text
    )
