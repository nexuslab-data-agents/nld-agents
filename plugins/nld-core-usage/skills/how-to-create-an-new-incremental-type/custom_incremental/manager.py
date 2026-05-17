"""State manager for `by_source_tst_with_days_from`.

The only behavioural difference from `by_source_tst` is the
`update_processing_state` override on DELTA runs: ``pull_from_timestamp``
is floored at ``now - days_from`` so that an old or missing watermark
backfills at least the last N days while a watermark older than the
floor is honoured.
"""

import datetime
from typing import Any, cast

from nld.connector.base.connector import DATA_CONNECTOR
from nld.flow.incremental.base.manager import (
    IncrementalBackendStateManager,
    IncrementalStateManager,
)
from nld.flow.incremental.base.sql_filter_manager import IncrementalSqlFilterManager
from nld.flow.utils import FlowLoadingStrategies
from nld.utils.datetime_util import get_current_datetime

from .logic import (
    BY_SOURCE_TST_WITH_DAYS_FROM_FLOW_INCREMENTAL_LOGIC,
    BySourceTstWithDaysFromFlowIncrementalParams,
)
from .sql_filter_manager import BySourceTstWithDaysFromSqlFilterManager
from .state import (
    BySourceTstWithDaysFromProcessingState,
    BySourceTstWithDaysFromSourceState,
    BySourceTstWithDaysFromState,
)


def _floor_with_days_from(
    watermark: datetime.datetime | None,
    days_from: int | None,
    now: datetime.datetime,
) -> datetime.datetime | None:
    """Floor a watermark at ``now - days_from``.

    Returns the older of ``watermark`` and ``now - days_from`` so the run
    pulls more, never less. When ``days_from`` is not set, the watermark
    is returned unchanged.
    """
    if days_from is None:
        return watermark
    floor = now - datetime.timedelta(days=days_from)
    if watermark is None:
        return floor
    return min(watermark, floor)


class BySourceTstWithDaysFromStateManager(
    IncrementalStateManager[
        BySourceTstWithDaysFromState,
        BySourceTstWithDaysFromSourceState,
        BySourceTstWithDaysFromProcessingState,
        BySourceTstWithDaysFromFlowIncrementalParams,
    ]
):
    flow_incremental_logic = BY_SOURCE_TST_WITH_DAYS_FROM_FLOW_INCREMENTAL_LOGIC

    def __init__(
        self,
        incremental_parameters: BySourceTstWithDaysFromFlowIncrementalParams,
        incremental_state_backend_manager: IncrementalBackendStateManager[
            DATA_CONNECTOR,
            BySourceTstWithDaysFromState,
            BySourceTstWithDaysFromSourceState,
            BySourceTstWithDaysFromProcessingState,
        ]
        | None = None,
        secondary_incremental_state_backend_manager: IncrementalBackendStateManager[
            DATA_CONNECTOR,
            BySourceTstWithDaysFromState,
            BySourceTstWithDaysFromSourceState,
            BySourceTstWithDaysFromProcessingState,
        ]
        | None = None,
        flow_parameters: dict[str, Any] | None = None,
    ):
        super().__init__(
            incremental_parameters=incremental_parameters,
            incremental_state_backend_manager=incremental_state_backend_manager,
            secondary_incremental_state_backend_manager=(
                secondary_incremental_state_backend_manager
            ),
            flow_parameters=flow_parameters,
        )
        self.processing_state: BySourceTstWithDaysFromProcessingState

    def init_processing_state(self) -> None:
        self.processing_state = BySourceTstWithDaysFromProcessingState(
            flow_uid=self.flow_uid,
            strategy=self.strategy,
        )

    def update_processing_state(self) -> None:
        assert self.latest_incremental_state is not None
        now = get_current_datetime()

        if self.strategy == FlowLoadingStrategies.DELTA:
            self.processing_state.pull_from_timestamp = _floor_with_days_from(
                watermark=self.latest_incremental_state.last_pull_to_timestamp,
                days_from=self.incremental_parameters.days_from,
                now=now,
            )
            self.processing_state.pull_to_timestamp = now
        elif self.strategy == FlowLoadingStrategies.FULL:
            self.processing_state.pull_from_timestamp = None
            self.processing_state.pull_to_timestamp = now
        elif self.strategy == FlowLoadingStrategies.BACKFILL:
            self.processing_state.pull_from_timestamp = (
                self.incremental_parameters.pull_from
            )
            self.processing_state.pull_to_timestamp = (
                self.incremental_parameters.pull_to
            )
        elif self.strategy == FlowLoadingStrategies.BACKFILL_DELTA:
            self.processing_state.pull_from_timestamp = (
                self.incremental_parameters.pull_from
            )
            self.processing_state.pull_to_timestamp = now
        else:
            raise NotImplementedError(
                f"The method 'update_processing_state' is not implemented "
                f"for data load strategy {self.strategy}"
            )

    @property
    def sql_filter_manager(self) -> IncrementalSqlFilterManager:
        return BySourceTstWithDaysFromSqlFilterManager(
            processing_state=self.processing_state,
        )

    _STATE_UPDATE_STRATEGIES = [
        FlowLoadingStrategies.DELTA,
        FlowLoadingStrategies.FULL,
        FlowLoadingStrategies.BACKFILL_DELTA,
    ]

    def create_post_processing_state(self) -> BySourceTstWithDaysFromState:
        self.post_processing_state = BySourceTstWithDaysFromState.deep_copy(
            cast(BySourceTstWithDaysFromState, self.latest_incremental_state)
        )

        if (
            self.processing_state.succeeded()
            and self.strategy in self._STATE_UPDATE_STRATEGIES
        ):
            self.post_processing_state.last_pull_to_timestamp = (
                self.processing_state.pull_to_timestamp
            )

        return self.post_processing_state
