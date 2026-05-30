"""Logic for the `by_source_tst_with_days_from` external incremental type.

Adds a single ``days_from: int | None`` parameter to ``by_source_tst``.
The parameter is consumed by the state manager to floor the next DELTA
pull at ``now - days_from``.
"""

import datetime
from typing import ClassVar

from pydantic import field_validator

from nld.flow.incremental.base.logic import (
    FULL_FLAG_PARAM,
    WITH_DELTA_FLAG_PARAM,
    FlowIncrementalDefinition,
    FlowIncrementalLogic,
    FlowIncrementalParamDefinition,
    FlowIncrementalParams,
)
from nld.flow.incremental.models.events import IncrementalParameterIgnored
from nld.flow.incremental.models.referential import (
    FlowSourceSelection,
    FlowTargetUpdateGranularity,
)
from nld.flow.utils import FlowLoadingStrategies
from nld.utils.datetime_util import ensure_utc_datetime, parse_datetime_string

from .state import (
    BySourceTstWithDaysFromProcessingState,
    BySourceTstWithDaysFromSourceState,
    BySourceTstWithDaysFromState,
)

PULL_FROM_PARAM = FlowIncrementalParamDefinition(
    name="pull_from",
    short_name="pull_from",
    data_type="datetime",
    mandatory=False,
    default_value=None,
    help_text="Override the start of the pull range (UTC datetime).",
)

PULL_TO_PARAM = FlowIncrementalParamDefinition(
    name="pull_to",
    short_name="pull_to",
    data_type="datetime",
    mandatory=False,
    default_value=None,
    help_text="Override the end of the pull range (UTC datetime).",
)

DAYS_FROM_PARAM = FlowIncrementalParamDefinition(
    name="days_from",
    short_name="days_from",
    data_type="int",
    mandatory=False,
    default_value=None,
    help_text=(
        "Floor the next DELTA pull at now - N days. The persisted watermark "
        "wins when it is older than now - N days; the floor wins otherwise."
    ),
)

BY_SOURCE_TST_WITH_DAYS_FROM_INCREMENTAL_DEFINITION = FlowIncrementalDefinition(
    default_strategy=FlowLoadingStrategies.DELTA,
    name="BY_SOURCE_TST_WITH_DAYS_FROM",
    category="by_source_tst_with_days_from",
    source_selection=FlowSourceSelection.BY_SOURCE_TST,
    target_update_granularity=FlowTargetUpdateGranularity.GENERIC,
    state_class=BySourceTstWithDaysFromState,
    source_state_class=BySourceTstWithDaysFromSourceState,
    processing_state_class=BySourceTstWithDaysFromProcessingState,
    auto_processing_state_transition=True,
    partial_state_persistence=False,
    tracks_logical_deletion=False,
    supports_planned_state=True,
    param_definitions=[
        FULL_FLAG_PARAM,
        PULL_FROM_PARAM,
        PULL_TO_PARAM,
        WITH_DELTA_FLAG_PARAM,
        DAYS_FROM_PARAM,
    ],
)


class BySourceTstWithDaysFromFlowIncrementalParams(FlowIncrementalParams):
    _definition: ClassVar[FlowIncrementalDefinition] = (
        BY_SOURCE_TST_WITH_DAYS_FROM_INCREMENTAL_DEFINITION
    )
    pull_from: datetime.datetime | None = None
    pull_to: datetime.datetime | None = None
    days_from: int | None = None

    @field_validator("pull_from", "pull_to", mode="before")
    @classmethod
    def parse_and_validate_utc_datetime(
        cls,
        value: datetime.datetime | str | None,
    ) -> datetime.datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            return parse_datetime_string(value)
        return ensure_utc_datetime(value)

    @field_validator("days_from")
    @classmethod
    def validate_days_from(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("days_from must be a positive integer")
        return value

    def resolve_strategy(self) -> str:
        if self.full:
            return FlowLoadingStrategies.FULL
        if self.pull_from is not None and self.pull_to is not None:
            return FlowLoadingStrategies.BACKFILL
        if self.pull_from is not None:
            return FlowLoadingStrategies.BACKFILL_DELTA
        return FlowLoadingStrategies.DELTA

    @classmethod
    def get_definition(cls) -> FlowIncrementalDefinition:
        return cls._definition

    def is_incremental_parameters_allowed(self) -> tuple[bool, str]:
        if self.strategy in [
            FlowLoadingStrategies.DELTA,
            FlowLoadingStrategies.FULL,
        ]:
            if self.pull_from is not None:
                self.log_event(
                    IncrementalParameterIgnored(
                        self.strategy,
                        parameter_name="pull_from",
                    )
                )
            if self.pull_to is not None:
                self.log_event(
                    IncrementalParameterIgnored(
                        self.strategy,
                        parameter_name="pull_to",
                    )
                )
            if (
                self.days_from is not None
                and self.strategy == FlowLoadingStrategies.FULL
            ):
                self.log_event(
                    IncrementalParameterIgnored(
                        self.strategy,
                        parameter_name="days_from",
                    )
                )
            return (True, "")
        if self.strategy in [
            FlowLoadingStrategies.BACKFILL,
            FlowLoadingStrategies.BACKFILL_DELTA,
        ]:
            if self.days_from is not None:
                self.log_event(
                    IncrementalParameterIgnored(
                        self.strategy,
                        parameter_name="days_from",
                    )
                )
            return (True, "")
        return (
            False,
            f"Strategy '{self.strategy}' is not supported for "
            f"'by_source_tst_with_days_from' incremental mode. "
            f"Supported strategies: DELTA, FULL, BACKFILL, BACKFILL-DELTA.",
        )


BY_SOURCE_TST_WITH_DAYS_FROM_FLOW_INCREMENTAL_LOGIC = FlowIncrementalLogic[
    BySourceTstWithDaysFromFlowIncrementalParams
](
    definition=BY_SOURCE_TST_WITH_DAYS_FROM_INCREMENTAL_DEFINITION,
    parameter_class=BySourceTstWithDaysFromFlowIncrementalParams,
)
