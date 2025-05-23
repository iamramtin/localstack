import json
from collections import OrderedDict

import pytest
from localstack_snapshot.snapshots.transformer import JsonpathTransformer, RegexTransformer

from localstack.aws.api.lambda_ import Runtime
from localstack.services.stepfunctions.asl.utils.json_path import extract_json
from localstack.testing.aws.util import is_aws_cloud
from localstack.testing.pytest import markers
from localstack.testing.pytest.stepfunctions.utils import (
    SfnNoneRecursiveParallelTransformer,
    await_execution_terminated,
    create_and_record_execution,
    create_state_machine_with_iam_role,
)
from localstack.utils.strings import short_uid
from tests.aws.services.stepfunctions.templates.errorhandling.error_handling_templates import (
    ErrorHandlingTemplate as EHT,
)
from tests.aws.services.stepfunctions.templates.scenarios.scenarios_templates import (
    ScenariosTemplate as ST,
)
from tests.aws.services.stepfunctions.templates.services.services_templates import (
    ServicesTemplates as SerT,
)


class TestBaseScenarios:
    @markers.snapshot.skip_snapshot_verify(paths=["$..cause"])
    @markers.aws.validated
    def test_catch_states_runtime(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_name = f"lambda_func_{short_uid()}"
        create_res = create_lambda_function(
            func_name=function_name,
            handler_file=SerT.LAMBDA_ID_FUNCTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "<lambda_function_name>"))
        function_arn = create_res["CreateFunctionResponse"]["FunctionArn"]

        template = ST.load_sfn_template(ST.CATCH_STATES_RUNTIME)
        template["States"]["RaiseRuntime"]["Resource"] = function_arn
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_catch_empty(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_name = f"lambda_func_{short_uid()}"
        create_res = create_lambda_function(
            func_name=function_name,
            handler_file=SerT.LAMBDA_ID_FUNCTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "<lambda_function_name>"))
        function_arn = create_res["CreateFunctionResponse"]["FunctionArn"]

        template = ST.load_sfn_template(ST.CATCH_EMPTY)
        template["States"]["StartTask"]["Resource"] = function_arn
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template",
        [
            ST.load_sfn_template(ST.PARALLEL_STATE),
            ST.load_sfn_template(ST.PARALLEL_STATE_PARAMETERS),
        ],
        ids=["PARALLEL_STATE", "PARALLEL_STATE_PARAMETERS"],
    )
    def test_parallel_state(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template,
    ):
        sfn_snapshot.add_transformer(SfnNoneRecursiveParallelTransformer())
        definition = json.dumps(template)
        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize("max_concurrency_value", [dict(), "NoNumber", 0, 1])
    def test_max_concurrency_path(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        max_concurrency_value,
    ):
        # TODO: Investigate AWS's behaviour with stringified integer values such as "1", as when passed as
        #  execution inputs these are casted to integers. Future efforts should record more snapshot tests to assert
        #  the behaviour of such stringification on execution inputs
        template = ST.load_sfn_template(ST.MAX_CONCURRENCY)
        definition = json.dumps(template)

        exec_input = json.dumps(
            {"MaxConcurrencyValue": max_concurrency_value, "Values": ["HelloWorld"]}
        )
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS consistently appears to stall after startup when a negative MaxConcurrency value is given.
            #  Instead, the Provider V2 raises a State.Runtime exception and terminates. In the future we should
            #  reevaluate AWS's behaviour in these circumstances and choose whether too also 'hang'.
            "$..events"
        ]
    )
    def test_max_concurrency_path_negative(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAX_CONCURRENCY)
        definition = json.dumps(template)

        exec_input = json.dumps({"MaxConcurrencyValue": -1, "Values": ["HelloWorld"]})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_parallel_state_order(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        sfn_snapshot.add_transformer(SfnNoneRecursiveParallelTransformer())
        template = ST.load_sfn_template(ST.PARALLEL_STATE_ORDER)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_parallel_state_fail(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.PARALLEL_STATE_FAIL)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input",
            "$..events..stateExitedEventDetails.output",
            "$..events..executionSucceededEventDetails.output",
        ]
    )
    def test_parallel_state_nested(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        sfn_snapshot.add_transformer(SfnNoneRecursiveParallelTransformer())
        template = ST.load_sfn_template(ST.PARALLEL_NESTED_NESTED)
        definition = json.dumps(template)

        exec_input = json.dumps([[1, 2, 3], [4, 5, 6]])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_parallel_state_catch(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.PARALLEL_STATE_CATCH)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_parallel_state_retry(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.PARALLEL_STATE_RETRY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_nested(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_NESTED)
        definition = json.dumps(template)

        exec_input = json.dumps(
            [
                [1, 2, 3],
                [4, 5, 6],
            ]
        )
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_no_processor_config(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_NO_PROCESSOR_CONFIG)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_legacy(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_legacy_config_inline(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY_CONFIG_INLINE)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_legacy_config_distributed(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY_CONFIG_DISTRIBUTED)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_legacy_config_distributed_parameters(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY_CONFIG_DISTRIBUTED_PARAMETERS)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_legacy_config_distributed_item_selector(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY_CONFIG_DISTRIBUTED_ITEM_SELECTOR)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_legacy_config_inline_parameters(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY_CONFIG_INLINE_PARAMETERS)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_legacy_config_inline_item_selector(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY_CONFIG_INLINE_ITEM_SELECTOR)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_config_distributed_item_selector(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_DISTRIBUTED_ITEM_SELECTOR)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # FIXME: AWS appears to have the state prior to MapStateExited as MapRunStarted.
            # LocalStack currently has this previous state as MapRunSucceeded.
            "$..events[8].previousEventId"
        ]
    )
    def test_map_state_config_distributed_item_selector_parameters(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_DISTRIBUTED_ITEM_SELECTOR_PARAMETERS)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_legacy_reentrant(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LEGACY_REENTRANT)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_config_distributed_reentrant(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        # Replace MapRunArns with fixed values to circumvent random ordering issues.
        sfn_snapshot.add_transformer(
            JsonpathTransformer(
                jsonpath="$..mapRunArn", replacement="map_run_arn", replace_reference=False
            )
        )

        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_DISTRIBUTED_REENTRANT)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_config_distributed_reentrant_lambda(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        # Replace MapRunArns with fixed values to circumvent random ordering issues.
        sfn_snapshot.add_transformer(
            JsonpathTransformer(
                jsonpath="$..mapRunArn", replacement="map_run_arn", replace_reference=False
            )
        )

        function_name = f"sfn_lambda_{short_uid()}"
        create_res = create_lambda_function(
            func_name=function_name,
            handler_file=SerT.LAMBDA_ID_FUNCTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "lambda_function_name"))
        function_arn = create_res["CreateFunctionResponse"]["FunctionArn"]

        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_DISTRIBUTED_REENTRANT_LAMBDA)
        definition = json.dumps(template)
        definition = definition.replace("_tbd_", function_arn)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_config_distributed_parameters(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_DISTRIBUTED_PARAMETERS)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_config_inline_item_selector(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_DISTRIBUTED_ITEM_SELECTOR)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: AWS appears to have changed json encoding to include spaces after separators,
            #  other v2 test suite snapshots need to be re-recorded
            "$..events..stateEnteredEventDetails.input"
        ]
    )
    def test_map_state_config_inline_parameters(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_INLINE_PARAMETERS)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template_path",
        [ST.MAP_STATE_ITEM_SELECTOR, ST.MAP_STATE_ITEM_SELECTOR_JSONATA],
        ids=["MAP_STATE_ITEM_SELECTOR", "MAP_STATE_ITEM_SELECTOR_JSONATA"],
    )
    def test_map_state_item_selector(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template_path,
    ):
        template = ST.load_sfn_template(template_path)
        definition = json.dumps(template)
        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    # FIXME: The previousEventId in the event history is incorrectly being set to the previous state
    @markers.snapshot.skip_snapshot_verify(paths=["$..events[2].previousEventId"])
    @pytest.mark.parametrize(
        "items_literal",
        [
            1,
            "'string'",
            "true",
            "{'foo': 'bar'}",
            "null",
            pytest.param(
                "$fn := function($x){$x}",
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(),
                    reason="LocalStack does not correctly handle when a higher-order function is passed as a parameter.",
                ),
            ),
        ],
        ids=["number", "string", "boolean", "object", "null", "function"],
    )
    @markers.aws.validated
    def test_map_state_items_eval_jsonata_fail(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        items_literal,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEMS_LITERAL)
        definition = json.dumps(template)
        definition = definition.replace("_tbd_", f"{{% {items_literal} %}}")

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @pytest.mark.parametrize(
        "items_literal",
        [[], [0], [1, "two", 3]],
        ids=["empty", "singleton", "mixed"],
    )
    @markers.aws.validated
    def test_map_state_items_eval_jsonata(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        items_literal,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEMS_LITERAL)
        definition = json.dumps(template)
        definition = definition.replace("_tbd_", f"{{% {items_literal} %}}")

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    # FIXME: The previousEventId in the event history is incorrectly being set to the previous state
    @markers.snapshot.skip_snapshot_verify(paths=["$..events[4].previousEventId"])
    @pytest.mark.parametrize(
        "items_literal",
        [1, "'string'", "true", "{'foo': 'bar'}", "null"],
        ids=["number", "string", "boolean", "object", "null"],
    )
    @markers.aws.validated
    def test_map_state_items_eval_jsonata_variable_sampling_fail(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        items_literal,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEMS_VARIABLE)
        definition = json.dumps(template)
        definition = definition.replace("_tbd_", f"{{% {items_literal} %}}")

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.snapshot.skip_snapshot_verify(
        paths=[
            # TODO: Create a function that maps Python types to JSONata type-strings
            "$..events[4].evaluationFailedEventDetails.cause",
            "$..events[6].executionFailedEventDetails.cause",
            # FIXME: The previousEventId in the event history is incorrectly being set to the previous state
            "$..events[4].previousEventId",
        ]
    )
    @pytest.mark.parametrize(
        "items_value",
        [1, "string", True, {"foo": "bar"}, None],
        ids=["number", "string", "boolean", "object", "null"],
    )
    @markers.aws.validated
    def test_map_state_items_input_types(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        items_value,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEMS)
        definition = json.dumps(template)

        exec_input = json.dumps({"items": items_value})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @pytest.mark.parametrize(
        "items_value",
        [[], [0], [1, "two", True]],
        ids=["empty", "singleton", "mixed"],
    )
    @markers.aws.validated
    def test_map_state_items_input_array(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        items_value,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEMS)
        definition = json.dumps(template)

        exec_input = json.dumps({"items": items_value})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.snapshot.skip_snapshot_verify(paths=["$..events[4].previousEventId"])
    @pytest.mark.parametrize(
        "items_literal",
        ["1", '"string"', "true", '{"foo": "bar"}', "null"],
        ids=["number", "string", "boolean", "object", "null"],
    )
    @markers.aws.validated
    def test_map_state_items_variable_sampling(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        items_literal,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEMS_VARIABLE)
        definition = json.dumps(template)
        definition = definition.replace('"_tbd_"', items_literal)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_item_selector_parameters(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEM_SELECTOR_PARAMETERS)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_parameters_legacy(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_PARAMETERS_LEGACY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_item_selector_singleton(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_ITEM_SELECTOR_SINGLETON)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_parameters_singleton_legacy(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_PARAMETERS_SINGLETON_LEGACY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_catch(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CATCH)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_catch_empty_fail(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CATCH_EMPTY_FAIL)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_catch_legacy(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CATCH_LEGACY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_retry(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_RETRY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_retry_multiple_retriers(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_RETRY_MULTIPLE_RETRIERS)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_retry_legacy(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_RETRY_LEGACY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_break_condition(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_BREAK_CONDITION)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_break_condition_legacy(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_BREAK_CONDITION_LEGACY)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "tolerance_template",
        [ST.MAP_STATE_TOLERATED_FAILURE_COUNT, ST.MAP_STATE_TOLERATED_FAILURE_PERCENTAGE],
        ids=["count_literal", "percentage_literal"],
    )
    def test_map_state_tolerated_failure_values(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        tolerance_template,
    ):
        template = ST.load_sfn_template(tolerance_template)
        definition = json.dumps(template)

        exec_input = json.dumps([0])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize("tolerated_failure_count_value", [dict(), "NoNumber", -1, 0, 1])
    def test_map_state_tolerated_failure_count_path(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        tolerated_failure_count_value,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_TOLERATED_FAILURE_COUNT_PATH)
        definition = json.dumps(template)

        exec_input = json.dumps(
            {"Items": [0], "ToleratedFailureCount": tolerated_failure_count_value}
        )
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "tolerated_failure_percentage_value", [dict(), "NoNumber", -1.1, -1, 0, 1, 1.1, 100, 100.1]
    )
    def test_map_state_tolerated_failure_percentage_path(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        tolerated_failure_percentage_value,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_TOLERATED_FAILURE_PERCENTAGE_PATH)
        definition = json.dumps(template)

        exec_input = json.dumps(
            {"Items": [0], "ToleratedFailurePercentage": tolerated_failure_percentage_value}
        )
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_label(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_LABEL)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(paths=["$..events[8].previousEventId"])
    def test_map_state_nested_config_distributed(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_NESTED_CONFIG_DISTRIBUTED)
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(paths=["$..events[8].previousEventId"])
    def test_map_state_nested_config_distributed_no_max_max_concurrency(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_name = f"lambda_func_{short_uid()}"
        create_lambda_function(
            func_name=function_name,
            handler_file=SerT.LAMBDA_ID_FUNCTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "<lambda_function_name>"))

        template = ST.load_sfn_template(ST.MAP_STATE_NESTED_CONFIG_DISTRIBUTED_NO_MAX_CONCURRENCY)
        definition = json.dumps(template)
        definition = definition.replace("__tbd__", function_name)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_state_result_writer(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = "result-bucket"
        s3_create_bucket(Bucket=bucket_name)

        template = ST.load_sfn_template(ST.MAP_STATE_RESULT_WRITER)
        definition = json.dumps(template)

        exec_input = json.dumps(["Hello", "World"])
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

        # Validate the manifest file
        # TODO: consider a better way to get MapRunArn
        map_run_arn = json.loads(
            sfn_snapshot.observed_state["get_execution_history"]["events"][-1][
                "executionSucceededEventDetails"
            ]["output"]
        )["MapRunArn"]
        map_run_uuid = map_run_arn.split(":")[-1]
        resp = aws_client.s3.get_object(
            Bucket=bucket_name, Key=f"mapJobs/{map_run_uuid}/manifest.json"
        )
        manifest_data = json.loads(resp["Body"].read().decode("utf-8"))
        assert manifest_data["DestinationBucket"] == bucket_name
        assert manifest_data["MapRunArn"] == map_run_arn
        assert manifest_data["ResultFiles"]["FAILED"] == []
        assert manifest_data["ResultFiles"]["PENDING"] == []
        assert manifest_data["ResultFiles"]["SUCCEEDED"] == []

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template_path",
        [
            ST.CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS,
            ST.CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS_JSONATA,
        ],
        ids=[
            "CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS",
            "CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS_JSONATA",
        ],
    )
    def test_choice_unsorted_parameters_positive(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template_path,
    ):
        template = ST.load_sfn_template(template_path)
        definition = json.dumps(template)
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            json.dumps({"result": {"done": True}}),
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template_path",
        [
            ST.CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS,
            ST.CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS_JSONATA,
        ],
        ids=[
            "CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS",
            "CHOICE_STATE_UNSORTED_CHOICE_PARAMETERS_JSONATA",
        ],
    )
    def test_choice_unsorted_parameters_negative(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template_path,
    ):
        template = ST.load_sfn_template(template_path)
        definition = json.dumps(template)
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            json.dumps({"result": {"done": False}}),
        )

    @markers.aws.validated
    def test_choice_condition_constant_jsonata(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.CHOICE_CONDITION_CONSTANT_JSONATA)
        definition = json.dumps(template)
        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template_path",
        [ST.CHOICE_STATE_AWS_SCENARIO, ST.CHOICE_STATE_AWS_SCENARIO_JSONATA],
        ids=["CHOICE_STATE_AWS_SCENARIO", "CHOICE_STATE_AWS_SCENARIO_JSONATA"],
    )
    def test_choice_aws_docs_scenario(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template_path,
    ):
        template = ST.load_sfn_template(template_path)
        definition = json.dumps(template)
        exec_input = json.dumps({"type": "Private", "value": 22})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template_path",
        [
            ST.CHOICE_STATE_SINGLETON_COMPOSITE,
            ST.CHOICE_STATE_SINGLETON_COMPOSITE_JSONATA,
            ST.CHOICE_STATE_SINGLETON_COMPOSITE_LITERAL_JSONATA,
        ],
        ids=[
            "CHOICE_STATE_SINGLETON_COMPOSITE",
            "CHOICE_STATE_SINGLETON_COMPOSITE_JSONATA",
            "CHOICE_STATE_SINGLETON_COMPOSITE_LITERAL_JSONATA",
        ],
    )
    def test_choice_singleton_composite(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template_path,
    ):
        template = ST.load_sfn_template(template_path)
        definition = json.dumps(template)
        exec_input = json.dumps({"type": "Public", "value": 22})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_base_list_objects_v2(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket_name"))
        for i in range(3):
            aws_client.s3.put_object(
                Bucket=bucket_name, Key=f"file_{i}.txt", Body=f"{i}HelloWorld!"
            )

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_LIST_OBJECTS_V2)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name})

        state_machine_arn = create_state_machine_with_iam_role(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
        )

        exec_resp = aws_client.stepfunctions.start_execution(
            stateMachineArn=state_machine_arn, input=exec_input
        )
        sfn_snapshot.add_transformer(sfn_snapshot.transform.sfn_sm_exec_arn(exec_resp, 0))
        execution_arn = exec_resp["executionArn"]

        await_execution_terminated(
            stepfunctions_client=aws_client.stepfunctions, execution_arn=execution_arn
        )

        execution_history = aws_client.stepfunctions.get_execution_history(
            executionArn=execution_arn
        )
        map_run_arn = extract_json("$..mapRunStartedEventDetails.mapRunArn", execution_history)
        sfn_snapshot.add_transformer(sfn_snapshot.transform.sfn_map_run_arn(map_run_arn, 0))

        # Normalise s3 ListObjectV2 response in the execution events output to ensure variable fields such as
        # Etag and LastModified are mapped to repeatable static values. Such normalisation is only necessary in
        # ItemReader calls invoking s3:ListObjectV2, of which result is directly mapped to the output of the iteration.
        output_str = execution_history["events"][-1]["executionSucceededEventDetails"]["output"]
        output_json = json.loads(output_str)
        output_norm = []
        for output_value in output_json:
            norm_output_value = OrderedDict()
            norm_output_value["Etag"] = f"<Etag-{output_value['Key']}>"
            norm_output_value["LastModified"] = "<date>"
            norm_output_value["Key"] = output_value["Key"]
            norm_output_value["Size"] = output_value["Size"]
            norm_output_value["StorageClass"] = output_value["StorageClass"]
            output_norm.append(norm_output_value)
        output_norm.sort(key=lambda value: value["Key"])
        output_norm_str = json.dumps(output_norm)
        execution_history["events"][-2]["stateExitedEventDetails"]["output"] = output_norm_str
        execution_history["events"][-1]["executionSucceededEventDetails"]["output"] = (
            output_norm_str
        )

        sfn_snapshot.match("get_execution_history", execution_history)

    @markers.aws.validated
    def test_map_item_reader_base_csv_headers_first_line(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_file = (
            "Col1,Col2,Col3\n"
            "Value1,Value2,Value3\n"
            "Value4,Value5,Value6\n"
            ",,,\n"
            "true,1,'HelloWorld'\n"
            "Null,None,\n"
            "   \n"
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_HEADERS_FIRST_LINE)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "max_items_value",
        [0, 2, 100_000_000],  # Linter on creation filters for valid input integers (0 - 100000000).
    )
    def test_map_item_reader_csv_max_items(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        max_items_value,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_file = "Col1,Col2\nValue1,Value2\nValue3,Value4\nValue5,Value6\nValue7,Value8\n"
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_MAX_ITEMS)
        template["States"]["MapState"]["ItemReader"]["ReaderConfig"]["MaxItems"] = max_items_value
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "max_items_value", [-1, 0, 1.5, 2, 100_000_000, 100_000_001]
    )  # The Distributed Map state stops reading items beyond 100_000_000.
    def test_map_item_reader_csv_max_items_paths(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        max_items_value,
    ):
        if max_items_value == 1.5:
            pytest.skip(
                "Validation of non integer max items value is performed at a higher depth than that of negative "
                "values in AWS StepFunctions. The SFN v2 interpreter runs this check at the same depth."
            )

        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_file = "Col1,Col2\nValue1,Value2\nValue3,Value4\nValue5,Value6\nValue7,Value8\n"
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_MAX_ITEMS_PATH)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key, "MaxItems": max_items_value})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @pytest.mark.skip_snapshot_verify(paths=["$..events[6].previousEventId"])
    @markers.aws.validated
    def test_map_item_reader_base_json_max_items_jsonata(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.json"
        json_file = json.dumps(
            [
                {"verdict": "true", "statement_date": "6/11/2008", "statement_source": "speech"},
                {
                    "verdict": "false",
                    "statement_date": "6/7/2022",
                    "statement_source": "television",
                },
                {
                    "verdict": "mostly-true",
                    "statement_date": "5/18/2016",
                    "statement_source": "news",
                },
            ]
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=json_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_JSON_MAX_ITEMS_JSONATA)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key, "MaxItems": 2})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @pytest.mark.skip(
        reason="TODO: Add JSONata support for ItemBatcher's MaxItemsPerBatch and MaxInputBytesPerBatch fields"
    )
    @markers.aws.validated
    def test_map_item_batching_base_json_max_per_batch_jsonata(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.json"
        json_file = json.dumps(
            [
                {"verdict": "true", "statement_date": "6/11/2008", "statement_source": "speech"},
                {
                    "verdict": "false",
                    "statement_date": "6/7/2022",
                    "statement_source": "television",
                },
                {
                    "verdict": "mostly-true",
                    "statement_date": "5/18/2016",
                    "statement_source": "news",
                },
            ]
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=json_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_BATCHER_BASE_JSON_MAX_PER_BATCH_JSONATA)
        definition = json.dumps(template)

        exec_input = json.dumps(
            {
                "Bucket": bucket_name,
                "Key": key,
                "MaxItemsPerBatch": 2,
                "MaxInputBytesPerBatch": 150_000,
            }
        )
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_base_csv_headers_decl(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_headers = ["H1", "H2", "H3"]
        csv_file = (
            "Value1,Value2,Value3\n"
            "Value4,Value5,Value6\n"
            ",,,\n"
            "true,1,'HelloWorld'\n"
            "Null,None,\n"
            "   \n"
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_HEADERS_DECL)
        template["States"]["MapState"]["ItemReader"]["ReaderConfig"]["CSVHeaders"] = csv_headers
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_csv_headers_decl_duplicate_headers(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_headers = ["H1", "H1", "H3"]
        csv_file = (
            "Value1,Value2,Value3\n"
            "Value4,Value5,Value6\n"
            ",,,\n"
            "true,1,'HelloWorld'\n"
            "Null,None,\n"
            "   \n"
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_HEADERS_DECL)
        template["States"]["MapState"]["ItemReader"]["ReaderConfig"]["CSVHeaders"] = csv_headers
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_csv_headers_first_row_typed_headers(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_file = "0,True,{}\nValue4,Value5,Value6\n,,,\ntrue,1,'HelloWorld'\nNull,None,\n   \n"
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_HEADERS_FIRST_LINE)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_csv_headers_decl_extra_fields(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_headers = ["H1"]
        csv_file = (
            "Value1,Value2,Value3\n"
            "Value4,Value5,Value6\n"
            ",,,\n"
            "true,1,'HelloWorld'\n"
            "Null,None,\n"
            "   \n"
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_HEADERS_DECL)
        template["States"]["MapState"]["ItemReader"]["ReaderConfig"]["CSVHeaders"] = csv_headers
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_csv_first_row_extra_fields(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.csv"
        csv_file = "H1,\nValue4,Value5,Value6\n,,,\ntrue,1,'HelloWorld'\nNull,None,\n   \n"
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=csv_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_CSV_HEADERS_FIRST_LINE)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_base_json(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.json"
        json_file = json.dumps(
            [
                {"verdict": "true", "statement_date": "6/11/2008", "statement_source": "speech"},
                {
                    "verdict": "false",
                    "statement_date": "6/7/2022",
                    "statement_source": "television",
                },
                {
                    "verdict": "mostly-true",
                    "statement_date": "5/18/2016",
                    "statement_source": "news",
                },
            ]
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=json_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_JSON)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "items_path",
        [
            "$.from_previous",
            "$[0]",
            "$.no_such_path_in_bucket_result",
        ],
        ids=[
            "VALID_ITEMS_PATH_FROM_PREVIOUS",
            "VALID_ITEMS_PATH_FROM_ITEM_READER",
            "INVALID_ITEMS_PATH",
        ],
    )
    @markers.snapshot.skip_snapshot_verify(paths=["$..previousEventId"])
    def test_map_item_reader_base_json_with_items_path(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        items_path,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.json"
        json_file = json.dumps([["from-bucket-item-0"]])
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=json_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_JSON_WITH_ITEMS_PATH)
        template["States"]["MapState"]["ItemsPath"] = items_path
        definition = json.dumps(template)

        exec_input = json.dumps(
            {"Bucket": bucket_name, "Key": key, "from_input_items": ["input-item-0"]}
        )
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(paths=["$..previousEventId"])
    def test_map_state_config_distributed_items_path_from_previous(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.MAP_STATE_CONFIG_DISTRIBUTED_ITEMS_PATH_FROM_PREVIOUS)
        definition = json.dumps(template)
        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_json_no_json_list_object(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.json"
        json_file = json.dumps({"Hello": "world"})
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=json_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_JSON)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_map_item_reader_base_json_max_items(
        self,
        aws_client,
        s3_create_bucket,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        bucket_name = s3_create_bucket()
        sfn_snapshot.add_transformer(RegexTransformer(bucket_name, "bucket-name"))

        key = "file.json"
        json_file = json.dumps(
            [
                {"verdict": "true", "statement_date": "6/11/2008", "statement_source": "speech"},
            ]
            * 3
        )
        aws_client.s3.put_object(Bucket=bucket_name, Key=key, Body=json_file)

        template = ST.load_sfn_template(ST.MAP_ITEM_READER_BASE_JSON_MAX_ITEMS)
        definition = json.dumps(template)

        exec_input = json.dumps({"Bucket": bucket_name, "Key": key})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.snapshot.skip_snapshot_verify(paths=["$..Cause"])
    @markers.aws.validated
    def test_lambda_empty_retry(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_name = f"lambda_func_{short_uid()}"
        create_res = create_lambda_function(
            func_name=function_name,
            handler_file=EHT.LAMBDA_FUNC_RAISE_EXCEPTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "<lambda_function_name>"))
        function_arn = create_res["CreateFunctionResponse"]["FunctionArn"]

        template = ST.load_sfn_template(ST.LAMBDA_EMPTY_RETRY)
        template["States"]["LambdaTask"]["Resource"] = function_arn
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.snapshot.skip_snapshot_verify(paths=["$..Cause"])
    @markers.aws.validated
    def test_lambda_invoke_with_retry_base(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_1_name = f"lambda_1_func_{short_uid()}"
        create_1_res = create_lambda_function(
            func_name=function_1_name,
            handler_file=EHT.LAMBDA_FUNC_RAISE_EXCEPTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_1_name, "<lambda_function_1_name>"))

        template = ST.load_sfn_template(ST.LAMBDA_INVOKE_WITH_RETRY_BASE)
        template["States"]["InvokeLambdaWithRetry"]["Resource"] = create_1_res[
            "CreateFunctionResponse"
        ]["FunctionArn"]
        definition = json.dumps(template)

        exec_input = json.dumps({"Value1": "HelloWorld!", "Value2": None})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.snapshot.skip_snapshot_verify(paths=["$..Cause"])
    @markers.aws.validated
    def test_lambda_invoke_with_retry_extended_input(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        sfn_snapshot.add_transformer(
            JsonpathTransformer(
                jsonpath="$..StartTime", replacement="<start-time>", replace_reference=False
            )
        )
        sfn_snapshot.add_transformer(
            JsonpathTransformer(
                jsonpath="$..EnteredTime", replacement="<entered-time>", replace_reference=False
            )
        )

        function_1_name = f"lambda_1_func_{short_uid()}"
        create_1_res = create_lambda_function(
            func_name=function_1_name,
            handler_file=EHT.LAMBDA_FUNC_RAISE_EXCEPTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_1_name, "<lambda_function_1_name>"))

        template = ST.load_sfn_template(ST.LAMBDA_INVOKE_WITH_RETRY_BASE_EXTENDED_INPUT)
        template["States"]["InvokeLambdaWithRetry"]["Resource"] = create_1_res[
            "CreateFunctionResponse"
        ]["FunctionArn"]
        definition = json.dumps(template)

        exec_input = json.dumps({"Value1": "HelloWorld!", "Value2": None})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.snapshot.skip_snapshot_verify(paths=["$..Cause"])
    @markers.aws.validated
    def test_lambda_service_invoke_with_retry_extended_input(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        sfn_snapshot.add_transformer(
            JsonpathTransformer(
                jsonpath="$..StartTime", replacement="<start-time>", replace_reference=False
            )
        )
        sfn_snapshot.add_transformer(
            JsonpathTransformer(
                jsonpath="$..EnteredTime", replacement="<entered-time>", replace_reference=False
            )
        )

        function_1_name = f"lambda_1_func_{short_uid()}"
        create_lambda_function(
            func_name=function_1_name,
            handler_file=EHT.LAMBDA_FUNC_RAISE_EXCEPTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_1_name, "<lambda_function_1_name>"))

        template = ST.load_sfn_template(ST.LAMBDA_SERVICE_INVOKE_WITH_RETRY_BASE_EXTENDED_INPUT)
        definition = json.dumps(template)

        exec_input = json.dumps(
            {"FunctionName": function_1_name, "Value1": "HelloWorld!", "Value2": None}
        )
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_retry_interval_features(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_name = f"lambda_func_{short_uid()}"
        create_res = create_lambda_function(
            func_name=function_name,
            handler_file=EHT.LAMBDA_FUNC_RAISE_EXCEPTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "<lambda_function_name>"))
        function_arn = create_res["CreateFunctionResponse"]["FunctionArn"]

        template = ST.load_sfn_template(ST.RETRY_INTERVAL_FEATURES)
        template["States"]["LambdaTask"]["Resource"] = function_arn
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_retry_interval_features_jitter_none(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_name = f"lambda_func_{short_uid()}"
        create_res = create_lambda_function(
            func_name=function_name,
            handler_file=EHT.LAMBDA_FUNC_RAISE_EXCEPTION,
            runtime=Runtime.python3_12,
        )
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "<lambda_function_name>"))
        function_arn = create_res["CreateFunctionResponse"]["FunctionArn"]

        template = ST.load_sfn_template(ST.RETRY_INTERVAL_FEATURES_JITTER_NONE)
        template["States"]["LambdaTask"]["Resource"] = function_arn
        definition = json.dumps(template)

        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_retry_interval_features_max_attempts_zero(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        create_lambda_function,
        sfn_snapshot,
    ):
        function_name = f"lambda_func_{short_uid()}"
        sfn_snapshot.add_transformer(RegexTransformer(function_name, "lambda_function_name"))
        create_lambda_function(
            func_name=function_name,
            handler_file=EHT.LAMBDA_FUNC_RAISE_EXCEPTION,
            runtime=Runtime.python3_12,
        )

        template = ST.load_sfn_template(ST.RETRY_INTERVAL_FEATURES_MAX_ATTEMPTS_ZERO)
        definition = json.dumps(template)

        exec_input = json.dumps({"FunctionName": function_name})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "timestamp_value",
        [
            "2016-03-14T01:59:00Z",
            "2016-03-05T21:29:29.243167252Z",
        ],
        ids=["SECONDS", "NANOSECONDS"],
    )
    def test_wait_timestamp(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        timestamp_value,
    ):
        template = ST.load_sfn_template(ST.WAIT_TIMESTAMP)
        template["States"]["WaitUntil"]["Timestamp"] = timestamp_value
        definition = json.dumps(template)
        exec_input = json.dumps({})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @markers.snapshot.skip_snapshot_verify(paths=["$..exception_value"])
    @pytest.mark.parametrize(
        "timestamp_value",
        [
            "2016-12-05 21:29:29Z",
            "2016-12-05T21:29:29",
            "2016-13-05T21:29:29Z",
            "2016-12-05T25:29:29Z",
            "05-12-2016T21:29:29Z",
            "{% '2016-03-14T01:59:00Z' %}",
        ],
        ids=["NO_T", "NO_Z", "INVALID_DATE", "INVALID_TIME", "INVALID_ISO", "JSONATA"],
    )
    def test_wait_timestamp_invalid(
        self,
        aws_client_no_retry,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        timestamp_value,
    ):
        template = ST.load_sfn_template(ST.WAIT_TIMESTAMP)
        template["States"]["WaitUntil"]["Timestamp"] = timestamp_value
        definition = json.dumps(template)
        with pytest.raises(Exception) as ex:
            create_state_machine_with_iam_role(
                aws_client_no_retry,
                create_state_machine_iam_role,
                create_state_machine,
                sfn_snapshot,
                definition,
            )
        sfn_snapshot.match(
            "exception", {"exception_typename": ex.typename, "exception_value": ex.value}
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "timestamp_value",
        [
            "2016-03-14T01:59:00Z",
            "2016-03-05T21:29:29.243167252Z",
            "2016-12-05 21:29:29Z",
            "2016-12-05T21:29:29",
            "2016-13-05T21:29:29Z",
            "2016-12-05T25:29:29Z",
            "05-12-2016T21:29:29Z",
        ],
        ids=[
            "SECONDS",
            "NANOSECONDS",
            "NO_T",
            "NO_Z",
            "INVALID_DATE",
            "INVALID_TIME",
            "INVALID_ISO",
        ],
    )
    def test_wait_timestamp_path(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        timestamp_value,
    ):
        template = ST.load_sfn_template(ST.WAIT_TIMESTAMP_PATH)
        definition = json.dumps(template)
        exec_input = json.dumps({"TimestampValue": timestamp_value})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "timestamp_value",
        [
            "2016-03-14T01:59:00Z",
            "2016-03-05T21:29:29.243167252Z",
            pytest.param(
                "2016-12-05 21:29:29Z",
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(), reason="depends on JSONata outcome validation"
                ),
            ),
            pytest.param(
                "2016-12-05T21:29:29",
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(), reason="depends on JSONata outcome validation"
                ),
            ),
            pytest.param(
                "2016-13-05T21:29:29Z",
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(), reason="depends on JSONata outcome validation"
                ),
            ),
            pytest.param(
                "2016-12-05T25:29:29Z",
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(), reason="depends on JSONata outcome validation"
                ),
            ),
            pytest.param(
                "05-12-2016T21:29:29Z",
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(), reason="depends on JSONata outcome validation"
                ),
            ),
        ],
        ids=[
            "SECONDS",
            "NANOSECONDS",
            "NO_T",
            "NO_Z",
            "INVALID_DATE",
            "INVALID_TIME",
            "INVALID_ISO",
        ],
    )
    def test_wait_timestamp_jsonata(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        timestamp_value,
    ):
        template = ST.load_sfn_template(ST.WAIT_TIMESTAMP_JSONATA)
        definition = json.dumps(template)
        exec_input = json.dumps({"TimestampValue": timestamp_value})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_wait_seconds_jsonata(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.WAIT_SECONDS_JSONATA)
        definition = json.dumps(template)

        exec_input = json.dumps({"waitSeconds": 0})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_fail_error_jsonata(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.RAISE_FAILURE_ERROR_JSONATA)
        definition = json.dumps(template)

        exec_input = json.dumps({"error": "Exception"})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    def test_fail_cause_jsonata(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
    ):
        template = ST.load_sfn_template(ST.RAISE_FAILURE_CAUSE_JSONATA)
        definition = json.dumps(template)

        exec_input = json.dumps({"cause": "This failed to due an Exception."})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template",
        [
            ST.load_sfn_template(ST.INVALID_JSONPATH_IN_ERRORPATH),
            ST.load_sfn_template(ST.INVALID_JSONPATH_IN_STRING_EXPR_JSONPATH),
            ST.load_sfn_template(ST.INVALID_JSONPATH_IN_STRING_EXPR_CONTEXTPATH),
            ST.load_sfn_template(ST.INVALID_JSONPATH_IN_CAUSEPATH),
            ST.load_sfn_template(ST.INVALID_JSONPATH_IN_INPUTPATH),
            ST.load_sfn_template(ST.INVALID_JSONPATH_IN_OUTPUTPATH),
            pytest.param(
                ST.load_sfn_template(ST.INVALID_JSONPATH_IN_TIMEOUTSECONDSPATH),
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(),
                    reason="timeout computation is run at the state's level",
                ),
            ),
            pytest.param(
                ST.load_sfn_template(ST.INVALID_JSONPATH_IN_HEARTBEATSECONDSPATH),
                marks=pytest.mark.skipif(
                    condition=not is_aws_cloud(),
                    reason="heartbeat computation is run at the state's level",
                ),
            ),
        ],
        ids=[
            "INVALID_JSONPATH_IN_ERRORPATH",
            "INVALID_JSONPATH_IN_STRING_EXPR_JSONPATH",
            "INVALID_JSONPATH_IN_STRING_EXPR_CONTEXTPATH",
            "ST.INVALID_JSONPATH_IN_CAUSEPATH",
            "ST.INVALID_JSONPATH_IN_INPUTPATH",
            "ST.INVALID_JSONPATH_IN_OUTPUTPATH",
            "ST.INVALID_JSONPATH_IN_TIMEOUTSECONDSPATH",
            "ST.INVALID_JSONPATH_IN_HEARTBEATSECONDSPATH",
        ],
    )
    def test_invalid_jsonpath(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template,
    ):
        definition = json.dumps(template)
        exec_input = json.dumps({"int-literal": 0})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.parametrize(
        "template_path",
        [
            ST.ESCAPE_SEQUENCES_STRING_LITERALS,
            ST.ESCAPE_SEQUENCES_JSONPATH,
            ST.ESCAPE_SEQUENCES_JSONATA_COMPARISON_OUTPUT,
            ST.ESCAPE_SEQUENCES_JSONATA_COMPARISON_ASSIGN,
        ],
        ids=[
            "ESCAPE_SEQUENCES_STRING_LITERALS",
            "ESCAPE_SEQUENCES_JSONPATH",
            "ESCAPE_SEQUENCES_JSONATA_COMPARISON_OUTPUT",
            "ESCAPE_SEQUENCES_JSONATA_COMPARISON_ASSIGN",
        ],
    )
    def test_escape_sequence_parsing(
        self,
        aws_client,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template_path,
    ):
        template = ST.load_sfn_template(template_path)
        definition = json.dumps(template)
        exec_input = json.dumps({'Test\\""Name"': 'Value"\\'})
        create_and_record_execution(
            aws_client,
            create_state_machine_iam_role,
            create_state_machine,
            sfn_snapshot,
            definition,
            exec_input,
        )

    @markers.aws.validated
    @pytest.mark.skip(
        reason=(
            "Lack of generalisable approach to escape sequences support "
            "in intrinsic functions literals; see backlog item."
        )
    )
    @pytest.mark.parametrize(
        "template_path",
        [
            ST.ESCAPE_SEQUENCES_ILLEGAL_INTRINSIC_FUNCTION,
            ST.ESCAPE_SEQUENCES_ILLEGAL_INTRINSIC_FUNCTION_2,
        ],
        ids=[
            "ESCAPE_SEQUENCES_ILLEGAL_INTRINSIC_FUNCTION",
            "ESCAPE_SEQUENCES_ILLEGAL_INTRINSIC_FUNCTION_2",
        ],
    )
    def test_illegal_escapes(
        self,
        aws_client_no_retry,
        create_state_machine_iam_role,
        create_state_machine,
        sfn_snapshot,
        template_path,
    ):
        template = ST.load_sfn_template(template_path)
        definition = json.dumps(template)
        with pytest.raises(Exception) as ex:
            create_state_machine_with_iam_role(
                aws_client_no_retry,
                create_state_machine_iam_role,
                create_state_machine,
                sfn_snapshot,
                definition,
            )
        sfn_snapshot.match(
            "exception", {"exception_typename": ex.typename, "exception_value": ex.value}
        )
