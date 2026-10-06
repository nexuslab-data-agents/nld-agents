"""State manager for `by_source_tst_with_days_from`.

The type behaves like `by_source_tst` except on DELTA runs:
``update_processing_state`` floors ``pull_from_timestamp`` at
``now - days_from``, so an absent or recent watermark backfills at least
the last N days, while a watermark older than the floor is honoured.
"""

import datetime
from typing import Any, cast

from nld.connector.base.connector import DataConnector
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
    BySourceTstWithDaysFromPlannedProcessingDetailedState,
    BySourceTstWithDaysFromPlannedProcessingState,
    BySourceTstWithDaysFromProcessingState,
    BySourceTstWithDaysFromSourceState,
    BySourceTstWithDaysFromState,
)

type BySourceTstWithDaysFromBackend = IncrementalBackendStateManager[
    DataConnector[Any],
    BySourceTstWithDaysFromState,
    BySourceTstWithDaysFromSourceState,
    BySourceTstWithDaysFromProcessingState,
    BySourceTstWithDaysFromPlannedProcessingState,
    BySourceTstWithDaysFromPlannedProcessingDetailedState,
]


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
        BySourceTstWithDaysFromPlannedProcessingState,
        BySourceTstWithDaysFromFlowIncrementalParams,
    ]
):
    flow_incremental_logic = BY_SOURCE_TST_WITH_DAYS_FROM_FLOW_INCREMENTAL_LOGIC

    def __init__(
        self,
        incremental_parameters: BySourceTstWithDaysFromFlowIncrementalParams,
        incremental_state_backend_manager: BySourceTstWithDaysFromBackend
        | None = None,
        secondary_incremental_state_backend_manager: BySourceTstWithDaysFromBackend
        | None = None,
        parameters: dict[str, Any] | None = None,
    ):
        super().__init__(
            incremental_parameters=incremental_parameters,
            incremental_state_backend_manager=incremental_state_backend_manager,
            secondary_incremental_state_backend_manager=(
                secondary_incremental_state_backend_manager
            ),
            parameters=parameters,
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

    def is_planned_processing_state_fresh(
        self,
        planned_processing_state: BySourceTstWithDaysFromPlannedProcessingState,
    ) -> bool:
        """Whether a plan still matches the latest baseline.

        BACKFILL and FULL windows are explicit and never go stale. A
        BACKFILL_DELTA plan is fresh when its last status change happened
        after the baseline ``last_pull_to_timestamp``. A DELTA plan adds that
        its floored ``pull_from_timestamp`` still covers that baseline.
        """
        detailed_state = planned_processing_state.detailed_state
        if detailed_state.strategy in [
            FlowLoadingStrategies.BACKFILL,
            FlowLoadingStrategies.FULL,
        ]:
            return True
        if self.latest_incremental_state is None:
            return True
        baseline_timestamp = self.latest_incremental_state.last_pull_to_timestamp
        plan_changed_after_last_run = (
            baseline_timestamp is None
            or planned_processing_state.status_changed_at > baseline_timestamp
        )
        if detailed_state.strategy == FlowLoadingStrategies.BACKFILL_DELTA:
            return plan_changed_after_last_run
        if detailed_state.strategy == FlowLoadingStrategies.DELTA:
            return plan_changed_after_last_run and (
                baseline_timestamp is None
                or (
                    detailed_state.pull_from_timestamp is not None
                    and detailed_state.pull_from_timestamp <= baseline_timestamp
                )
            )
        return True

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
