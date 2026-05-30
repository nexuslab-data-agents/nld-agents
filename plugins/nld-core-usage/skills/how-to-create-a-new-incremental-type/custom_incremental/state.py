"""State models for the `by_source_tst_with_days_from` external incremental type.

The persisted watermark is identical to `by_source_tst`: a single
``last_pull_to_timestamp`` per flow. ``days_from`` is a runtime parameter
only; it does not alter what gets stored.
"""

import datetime

from pydantic import field_validator

from nld.flow.incremental.base.state import (
    FlowProcessingState,
    FlowSourceState,
    FlowState,
)
from nld.flow.incremental.models.referential import (
    IncrementalProcessingStatus,
)
from nld.utils.datetime_util import ensure_utc_datetime, get_current_datetime


class BySourceTstWithDaysFromState(FlowState):
    last_pull_to_timestamp: datetime.datetime | None = None

    @field_validator("last_pull_to_timestamp", mode="before")
    @classmethod
    def validate_utc_timezone(
        cls,
        value: datetime.datetime | None,
    ) -> datetime.datetime | None:
        return ensure_utc_datetime(value)


class BySourceTstWithDaysFromSourceState(FlowSourceState):
    pass


class BySourceTstWithDaysFromProcessingState(FlowProcessingState):
    pull_from_timestamp: datetime.datetime | None = None
    pull_to_timestamp: datetime.datetime | None = None
    processing_status: str = IncrementalProcessingStatus.TO_BE_PROCESSED
    process_error_message: str | None = None
    processing_completed_at: datetime.datetime | None = None

    @field_validator(
        "pull_from_timestamp",
        "pull_to_timestamp",
        "processing_completed_at",
        mode="before",
    )
    @classmethod
    def validate_utc_timezone(
        cls,
        value: datetime.datetime | None,
    ) -> datetime.datetime | None:
        return ensure_utc_datetime(value)

    def set_to_be_processed(self) -> None:
        self.processing_status = IncrementalProcessingStatus.TO_BE_PROCESSED

    def set_to_succeeded(self) -> None:
        self.processing_status = IncrementalProcessingStatus.SUCCEEDED
        self.process_error_message = None
        self.processing_completed_at = get_current_datetime()

    def set_to_failed(self, error_message: str | None = None) -> None:
        self.processing_status = IncrementalProcessingStatus.FAILED
        self.process_error_message = error_message
        self.processing_completed_at = get_current_datetime()

    def get_pull_timestamps(
        self,
    ) -> tuple[datetime.datetime | None, datetime.datetime | None]:
        return self.pull_from_timestamp, self.pull_to_timestamp

    def get_display_log(self) -> str:
        if self.pull_from_timestamp is not None and self.pull_to_timestamp is not None:
            range_display = f"[{self.pull_from_timestamp} → {self.pull_to_timestamp}]"
        elif self.pull_from_timestamp is None and self.pull_to_timestamp is not None:
            range_display = f"[→ {self.pull_to_timestamp}]"
        else:
            range_display = "no range"
        return f"Strategy: {self.strategy} | Range: {range_display}"

    def to_be_processed(self) -> bool:
        return self.processing_status == IncrementalProcessingStatus.TO_BE_PROCESSED

    def succeeded(self) -> bool:
        return self.processing_status == IncrementalProcessingStatus.SUCCEEDED

    def failed(self) -> bool:
        return self.processing_status == IncrementalProcessingStatus.FAILED
