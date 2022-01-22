#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import argparse
import boto3
import botocore
import json
import logging
import os
import time
import traceback
from .version import __version__

logging.basicConfig(format="%(message)s")
logger = logging.getLogger("")
logger.setLevel("WARNING")


class TestFailure(Exception):
    pass


class Stack:
    OUTPUT_KEYS = {
        "CONFIG_RULE_NAME": "ConfigRuleName",
        "COMPLIANT_RESOURCE_IDS": "CompliantResourceIds",
        "NON_COMPLIANT_RESOURCE_IDS": "NonCompliantResourceIds",
        "NOT_APPLICABLE_RESOURCE_IDS": "NotApplicableResourceIds",
        "DELAY_AFTER_DEPLOY": "DelayAfterDeploy",
        "SKIP_WAIT_FOR_RESOURCE_RECORDING": "SkipWaitForResourceRecording",
    }

    OUTPUTS_DEFAULTS = {
        OUTPUT_KEYS["CONFIG_RULE_NAME"]: "",
        OUTPUT_KEYS["COMPLIANT_RESOURCE_IDS"]: "",
        OUTPUT_KEYS["NON_COMPLIANT_RESOURCE_IDS"]: "",
        OUTPUT_KEYS["NOT_APPLICABLE_RESOURCE_IDS"]: "",
        OUTPUT_KEYS["DELAY_AFTER_DEPLOY"]: 0,
        OUTPUT_KEYS["SKIP_WAIT_FOR_RESOURCE_RECORDING"]: "False",
    }

    EXPECTED_COMPLIANCE_TYPE_LOOKUP = {
        OUTPUT_KEYS["COMPLIANT_RESOURCE_IDS"]: "COMPLIANT",
        OUTPUT_KEYS["NON_COMPLIANT_RESOURCE_IDS"]: "NON_COMPLIANT",
        OUTPUT_KEYS["NOT_APPLICABLE_RESOURCE_IDS"]: "NOT_APPLICABLE",
    }

    CFN_WAITER_CONFIG = {"Delay": 15}
    AWS_CONFIG_API_DELAY_SEC = 15

    TRIGGER_RULE_EVALUATION_ARG = "--trigger-rule-evaluation"

    DELETE_STACK_ARG = "--delete-stack"
    DELETE_STACK_ALWAYS = "Always"
    DELETE_STACK_ON_SUCCESS = "OnSuccess"
    DELETE_STACK_NEVER = "Never"
    # Default behavior b/c it makes most sense for local usage and first exposure to the tool
    # TODO: default behavior for CI pipelines:
    #     if not sys.__stdin__.isatty() and not sys.__stdout__.isatty():
    #         default = 'Always`
    DELETE_STACK_DEFAULT = DELETE_STACK_ON_SUCCESS
    DELETE_STACK_CHOICES = [
        DELETE_STACK_ALWAYS,
        DELETE_STACK_ON_SUCCESS,
        DELETE_STACK_NEVER,
    ]

    def parse_args(self, args):
        parser = argparse.ArgumentParser(description=f"critter {__version__} - AWS Config Rule Integration TesTER")

        parser.add_argument(
            "template",
            metavar="TEMPLATE",
            help="CloudFormation template(s) to test already deployed Config rule",
        )

        parser.add_argument(
            "--log-level",
            dest="log_level",
            help="Specify log level - 'debug' will include boto3 debug logs",
            default="info",
            choices=["debug", "info", "warning"],
        )

        # TODO: this might make more sense in a test stack output
        parser.add_argument(
            self.TRIGGER_RULE_EVALUATION_ARG,
            help=(
                "Trigger Config rule evaluation after CloudFormation stack deployment. Useful for "
                "periodic evaluation rules. Also ensures the rule evaluation occured after stack deployment."
            ),
            dest="trigger_rule_evaluation",
            action="store_true",
        )
        parser.set_defaults(trigger_rule_evaluation=False)

        # TODO: --stack-name-prefix argument

        parser.add_argument(
            "--stack-name",
            metavar="STACK-NAME",
            help="CloudFormation stack name (default is generated from TEMPLATE file name)",
        )

        parser.add_argument(
            "--stack-tags",
            metavar='\'[{"Key": "TagKey", "Value": "TagValue"}, ...]\'',
            type=json.loads,
            default="[]",
            help="Tags to associate with the CloudFormation stack formatted as a JSON string",
        )

        parser.add_argument(
            "--capabilities",
            default=[],
            metavar="CAPABILITY",
            nargs="+",
            help="CloudFormation capabilities needed to deploy the stack (i.e. CAPABILITY_IAM, CAPABILITY_NAMED_IAM)",
        )

        parser.add_argument(
            self.DELETE_STACK_ARG,
            help=(
                "Test outcome that should trigger CloudFormation stack delete "
                f"(default: {self.DELETE_STACK_DEFAULT})"
            ),
            default=self.DELETE_STACK_DEFAULT,
            choices=self.DELETE_STACK_CHOICES,
        )
        parsed_args = parser.parse_args(args)

        logger.setLevel(parsed_args.log_level.upper())

        self.template_file = parsed_args.template
        template_filename = os.path.splitext(os.path.basename(self.template_file))[0]
        with open(self.template_file) as f:
            self.template_body = f.read()

        if parsed_args.stack_name:
            self.stack_name = parsed_args.stack_name
        else:
            self.stack_name = "Critter-" + template_filename.replace("_", "-")

        if parsed_args.delete_stack not in self.DELETE_STACK_CHOICES:
            raise Exception(
                f"Error - delete_stack must be one of {self.DELETE_STACK_CHOICES}, "
                f"received '{parsed_args.delete_stack}'"
            )
        self.delete_stack = parsed_args.delete_stack

        if parsed_args.stack_tags:
            self.stack_tags = parsed_args.stack_tags
        else:
            self.stack_tags = [
                {"Key": "ConfigRuleTesting", "Value": "True"},
                {"Key": "Critter", "Value": "True"},
            ]

        self.cfn_capabilities = parsed_args.capabilities
        # TODO: default trigger_rule_evaluation to True if rule detected as periodic evaluation only
        #       or if stack already exists
        self.trigger_rule_evaluation = parsed_args.trigger_rule_evaluation

    def initialize_boto_clients(self):
        self.sts = boto3.client("sts")
        self.cfn = boto3.client("cloudformation")
        self.config = boto3.client("config")

    def test(self):
        """The main entrypoint into executing a critter test. This function is called from /bin/critter"""

        logger.info(f"Testing using identity '{self.sts.get_caller_identity()['Arn']}'")
        err = None
        try:
            self.deploy()
            self.process_outputs()
            self.wait_for_config_resources()
            self.start_config_rule_evaluation()
            self.wait_for_config_evaluation()
            self.validate_config_evaluation()
        except TestFailure as e:
            logger.error(
                f"\u274c Config rule '{self.config_rule_name}' test failed! One or more resources "
                "were evaluated by AWS Config with an unexpected compliance type.",
            )
            logger.error(e)
            print()  # printing a blank line for console output readability
            err = e
        except (Exception, KeyboardInterrupt) as e:
            logger.error("\nCritter encountered an error:\n")
            logger.error(traceback.format_exc())
            err = e
        else:
            logger.error(f"\u2705 Config rule '{self.config_rule_name}' test passed!\n")
        finally:
            no_delete_msg = (
                f"Not deleting CloudFormation stack '{self.stack_name}', specify '{self.DELETE_STACK_ARG}' "
                "to control this behavior"
            )
            if err:
                if self.delete_stack == self.DELETE_STACK_ALWAYS:
                    self.delete()
                else:
                    logger.info(no_delete_msg)
                exit(1)

            if self.delete_stack != self.DELETE_STACK_NEVER:
                self.delete()
            else:
                logger.info(no_delete_msg)

    def deploy(self):
        logger.info(f"Deploying CloudFormation template '{self.template_file}' as stack '{self.stack_name}'")
        self.deploy_action_performed = None
        try:
            self.cfn.create_stack(
                StackName=self.stack_name,
                TemplateBody=self.template_body,
                OnFailure="DELETE",
                Capabilities=self.cfn_capabilities,
                Tags=self.stack_tags,
            )

            logger.info(f"Waiting for CloudFormation stack '{self.stack_name}' creation to complete")
            self.cfn.get_waiter("stack_create_complete").wait(
                StackName=self.stack_name, WaiterConfig=self.CFN_WAITER_CONFIG
            )
            self.deploy_action_performed = "CREATE"
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AlreadyExistsException":
                self.update()
            elif e.response["Error"]["Code"] == "InsufficientCapabilitiesException":
                logger.error("Error - Specify required CloudFormation capabilities with '--capabilities CAPABILITY'")
                raise e
            else:
                raise e

        self.stack = boto3.resource("cloudformation").Stack(self.stack_name)
        logger.info(f"Deployed CloudFormation stack '{self.stack.stack_id}'")

    def update(self):
        logger.warning(
            f"Warning - Updating existing CloudFormation stack '{self.stack_name}'. Testing using existing stacks may "
            "result in unreliable test results. It is recommended to deploy a new stack for each test iteration."
        )
        if not self.trigger_rule_evaluation:
            logger.warning(
                "Warning - Updating an existing CloudFormation stack without specifying "
                f"'{self.TRIGGER_RULE_EVALUATION_ARG}' may result in the Config rule evaluation never occurring."
            )
        try:
            self.cfn.update_stack(
                StackName=self.stack_name,
                TemplateBody=self.template_body,
                DisableRollback=True,
                Capabilities=self.cfn_capabilities,
                Tags=self.stack_tags,
            )

            logger.info(f"Waiting for CloudFormation stack '{self.stack_name}' update to complete")
            self.cfn.get_waiter("stack_update_complete").wait(
                StackName=self.stack_name, WaiterConfig=self.CFN_WAITER_CONFIG
            )
            self.deploy_action_performed = "UPDATE"
        except botocore.exceptions.ClientError as e:
            if "No updates are to be performed" in e.response["Error"]["Message"]:
                logger.info(f"No updates are to be performed on CloudFormation stack '{self.stack_name}'")
            elif e.response["Error"]["Code"] == "InsufficientCapabilitiesException":
                logger.error("Error - Specify required CloudFormation capabilities with '--capabilities CAPABILITY'")
                raise e
            else:
                raise e

    def process_outputs(self):
        # Save stack outputs in an easy access dict
        self.stack_outputs = self.OUTPUTS_DEFAULTS.copy()
        for o in self.stack.outputs:
            self.stack_outputs[o["OutputKey"]] = o["OutputValue"]

        # Sleep for DelayAfterDeploy immediately after loading stack outputs
        self.delay_after_deploy = int(self.stack_outputs[self.OUTPUT_KEYS["DELAY_AFTER_DEPLOY"]])
        if self.delay_after_deploy and self.deploy_action_performed:
            logger.info(f"Sleeping {self.delay_after_deploy} seconds")
            time.sleep(self.delay_after_deploy)

        self.config_rule_name = self.stack_outputs[self.OUTPUT_KEYS["CONFIG_RULE_NAME"]].strip()
        if self.config_rule_name == self.OUTPUTS_DEFAULTS[self.OUTPUT_KEYS["CONFIG_RULE_NAME"]]:
            raise Exception(
                f"Error - Missing required output '{self.OUTPUT_KEYS['CONFIG_RULE_NAME']}' "
                f"on CloudFormation stack '{self.stack_name}'"
            )

        try:
            self.config_rule = self.config.describe_config_rules(ConfigRuleNames=[self.config_rule_name])[
                "ConfigRules"
            ][0]
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchConfigRuleException":
                raise Exception(f"Error - Config rule '{self.config_rule_name}' not found!")
            else:
                raise e

        self.resources = {}
        resource_ids_output_keys = self.EXPECTED_COMPLIANCE_TYPE_LOOKUP.keys()
        for output_key in resource_ids_output_keys:
            resource_ids_csv = self.stack_outputs[output_key]
            if not resource_ids_csv:
                # Empty string means cfn stack did not declare the output
                continue
            for r_id in [i.strip() for i in resource_ids_csv.split(",")]:
                expected_compliance_type = self.EXPECTED_COMPLIANCE_TYPE_LOOKUP[output_key]
                if expected_compliance_type == "NOT_APPLICABLE":
                    logger.warning(
                        "Warning - Testing for NOT_APPLICABLE compliance type is experimental and "
                        "may yield unexpected results."
                    )
                if r_id in self.resources.keys():
                    raise Exception(f"Error - Resource id '{r_id}' declared in multiple outputs")
                self.resources[r_id] = {
                    "expected_compliance_type": expected_compliance_type,
                    "evaluation_result": {},
                }

        if not self.resources:
            raise Exception(
                "Error - Did not find any resource ids outputs. Specify one or more of the following "
                f"CloudFormation stack outputs: {list(resource_ids_output_keys)}"
            )

        # TODO: load resource types from test stack output if not provided in rule scope attribute
        self.resource_types = self.config_rule["Scope"]["ComplianceResourceTypes"]

        self.skip_wait_for_resource_recording = (
            self.stack_outputs[self.OUTPUT_KEYS["SKIP_WAIT_FOR_RESOURCE_RECORDING"]].lower() == "true"
        )

    def wait_for_config_resources(self):
        skip_msg = "Skipping waiting for resources to be recorded by AWS Config"
        if self.skip_wait_for_resource_recording:
            logger.info(skip_msg)
            return
        if not self.resource_types:
            logger.warning(
                f"Warning - {skip_msg}. Config rule '{self.config_rule_name}' scope does not specify "
                "applicable resource types."
            )
            return

        logger.info(f"Waiting for {len(self.resources)} resources to be recorded by AWS Config")
        logger.info(
            f"Searching for resource types {self.resource_types} and resource ids {list(self.resources.keys())}"
        )

        resource_keys = []
        for r_id in self.resources.keys():
            for r_type in self.resource_types:
                resource_keys.append({"resourceType": r_type, "resourceId": r_id})

        found_config_resources = []
        loop = 0
        while len(found_config_resources) != len(self.resources):
            if loop:
                time.sleep(self.AWS_CONFIG_API_DELAY_SEC)

            found_config_resources = self.config.batch_get_resource_config(resourceKeys=resource_keys)[
                "baseConfigurationItems"
            ]
            logger.info(f"Found {len(found_config_resources)} resources recorded by AWS Config")

            # TODO: if loop has run for longer than is typically expected, print help message
            # if loop * self.AWS_CONFIG_API_DELAY_SEC > 180:
            #     logger.warning(
            #         "Warning - Still waiting for resources to be recorded by AWS Config. Ensure "
            #         f"{self.resource_types} are recorded by AWS Config or consider specifying the critter test stack "
            #         f"output '{self.OUTPUT_KEYS['SKIP_WAIT_FOR_RESOURCE_RECORDING']}'."
            #     )

            loop += 1

    def start_config_rule_evaluation(self):
        if not self.trigger_rule_evaluation:
            return

        logger.info(f"Triggering Config rule '{self.config_rule_name}' evaluation")
        try:
            self.config.start_config_rules_evaluation(ConfigRuleNames=[self.config_rule_name])
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "LimitExceededException":
                logger.info(
                    "Encountered LimitExceededException when calling Config StartConfigRulesEvaluation api, "
                    "sleeping before retry"
                )
                time.sleep(self.AWS_CONFIG_API_DELAY_SEC)
                self.start_config_rule_evaluation()
            else:
                raise e

    def wait_for_config_evaluation(self):
        for r_id in list(self.resources.keys()):
            if self.resources[r_id]["expected_compliance_type"] == "NOT_APPLICABLE":
                # TODO: Determine some way to test for this. NOT_APPLICABLE evaluations are not stored by Config.
                #       Search thru recent PutEvaluations events in CloudTrail and look for the resource id?
                logger.warning(
                    f"Warning - Verifying resource '{r_id}' compliance 'NOT_APPLICABLE' is not yet implemented"
                )
                self.resources.pop(r_id)
                break

        last_stack_event_timestamp = list(self.stack.events.limit(count=1))[0].timestamp

        # TODO: This loop may be unnecessary. This loop waits for the Config rule evaluation to succeed. The loop below
        #       waits for the each of the test resources to be evaluated.
        logger.info(f"Waiting for Config rule '{self.config_rule_name}' successful evaluation")
        loop = 0
        while True:
            if loop or self.trigger_rule_evaluation:
                time.sleep(self.AWS_CONFIG_API_DELAY_SEC)
            loop += 1

            status = self.config.describe_config_rule_evaluation_status(ConfigRuleNames=[self.config_rule_name])[
                "ConfigRulesEvaluationStatus"
            ][0]

            if "LastSuccessfulInvocationTime" not in status:
                logger.warning(
                    f"Warning - Waiting for first successful evaluation of Config rule '{self.config_rule_name}'"
                )
                continue

            if "LastFailedInvocationTime" in status:
                if status["LastFailedInvocationTime"] > status["LastSuccessfulInvocationTime"]:
                    logger.warning(f"Warning - Config rule '{self.config_rule_name}' most recent invocation failed")

                last_invocation_time = max(status["LastFailedInvocationTime"], status["LastSuccessfulInvocationTime"])
            else:
                last_invocation_time = status["LastSuccessfulInvocationTime"]

            if loop >= 3:
                logger.info(
                    f"Still waiting for Config rule '{self.config_rule_name}' successful evaluation. "
                    f"Evaluation status: {json.dumps(status, default=str)}"
                )

            if status["LastSuccessfulEvaluationTime"] > last_invocation_time:
                break

        loop = 0
        unevaluated_resource_ids = list(self.resources.keys())
        while len(unevaluated_resource_ids):
            logger.info(
                f"Waiting for Config rule '{self.config_rule_name}' evaluation of "
                f"resource ids {unevaluated_resource_ids}"
            )
            if loop:
                time.sleep(self.AWS_CONFIG_API_DELAY_SEC)
            loop += 1

            for pg in self.config.get_paginator("get_compliance_details_by_config_rule").paginate(
                ConfigRuleName=self.config_rule_name
            ):
                for result in pg["EvaluationResults"]:
                    qualifier = result["EvaluationResultIdentifier"]["EvaluationResultQualifier"]
                    r_id = qualifier["ResourceId"]

                    if r_id not in self.resources.keys():
                        continue

                    self.resources[r_id]["resource_type"] = qualifier["ResourceType"]

                    # Warn the user if evaluation result was posted before stack deploy finished
                    if result["ResultRecordedTime"] < last_stack_event_timestamp:
                        logger.warning(
                            f"Warning - Resource '{r_id}' Config evaluation was recorded before the most recent event "
                            f"on CloudFormation stack '{self.stack_name}'. This may be an indicator of unreliable test "
                            f"results. Consider specifying '{self.TRIGGER_RULE_EVALUATION_ARG}'."
                        )
                    self.resources[r_id]["evaluation_result"] = result

            unevaluated_resource_ids = []
            for r_id in self.resources.keys():
                if not self.resources[r_id]["evaluation_result"]:
                    unevaluated_resource_ids.append(r_id)

    def validate_config_evaluation(self):
        logger.info(f"Validating Config rule '{self.config_rule_name}' evaluation results")

        print()  # printing a blank line for console output readability
        failed_resource_ids = []
        for resource_id, resource in self.resources.items():
            resource_type = resource["resource_type"]
            expected = resource["expected_compliance_type"]
            actual = resource["evaluation_result"]["ComplianceType"]

            # TODO: test for expected annotation values

            if expected == actual:
                emoji = "\u2705"
            else:
                emoji = "\u274c"
                failed_resource_ids.append(resource_id)

            try:
                annotation = resource["evaluation_result"]["Annotation"]
            except KeyError:
                annotation = "<None>"
            logger.warning(
                f"{emoji}\tResource type: {resource_type}\n\tResource id:   {resource_id}\n"
                f"\tExpected:      {expected}\n\tActual:        {actual}\n\tAnnotation:    {annotation}"
            )

        print()  # printing a blank line for console output readability

        if failed_resource_ids:
            raise TestFailure(f"Failed resource ids: {failed_resource_ids}")

    def delete(self):
        logger.info(
            f"Deleting CloudFormation stack '{self.stack_name}' - specify '{self.DELETE_STACK_ARG}' "
            "to control this behavior"
        )
        self.cfn.delete_stack(StackName=self.stack_name)
        logger.info(f"Waiting for CloudFormation stack '{self.stack_name}' delete to complete")
        self.cfn.get_waiter("stack_delete_complete").wait(
            StackName=self.stack_name, WaiterConfig=self.CFN_WAITER_CONFIG
        )
        logger.info(f"Deleted CloudFormation stack '{self.stack_name}'")
