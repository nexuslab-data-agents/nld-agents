"""PostgreSQL backend for `by_source_tst_with_days_from`.

Persists state, processing-state and planned-state rows through the
``Psycopg2SQLConnector`` model manager. The watermark schema matches the
built-in ``PostgreSQLBySourceTstStateBackendManager``; only the table
names differ.

``PostgreSQLIncrementalBackendMixin`` makes the backend plan-capable
(``supports_planned_state = True``) and owns the shared state-plan table;
the backend supplies the type's own planned processing-state table through
``_ensure_planned_processing_state_table_exists``,
``write_planned_processing_state`` and ``read_planned_processing_state``.
"""

import datetime
from typing import Any, cast

from pydantic import ConfigDict, Field, field_validator

from nld.connector.postgresql.engine.psycopg2.connector import (
    Psycopg2SQLConnector,
)
from nld.flow.backend.postgresql.utils import PSQL_BACKEND_INCREMENTAL_TABLE_PREFIX
from nld.flow.incremental.backend.postgresql import PostgreSQLIncrementalBackendMixin
from nld.pydantic import NldBaseModel
from nld.utils.datetime_util import normalize_to_utc

from ..state import (
    BySourceTstWithDaysFromPlannedProcessingDetailedState,
    BySourceTstWithDaysFromProcessingState,
    BySourceTstWithDaysFromState,
)
from .base_with_pydantic import BySourceTstWithDaysFromStateBackendManager

PSQL_STATE_TABLE_NAME = (
    f"{PSQL_BACKEND_INCREMENTAL_TABLE_PREFIX}_by_source_tst_with_days_from_state"
)
PSQL_PROCESSING_STATE_TABLE_NAME = (
    f"{PSQL_BACKEND_INCREMENTAL_TABLE_PREFIX}"
    "_by_source_tst_with_days_from_processing_state"
)
PSQL_PLANNED_PROCESSING_STATE_TABLE_NAME = (
    f"{PSQL_BACKEND_INCREMENTAL_TABLE_PREFIX}"
    "_plans_by_source_tst_with_days_from_planned_processing_state"
)


class BySourceTstWithDaysFromStateRow(NldBaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "functional_key": {
                "fields": ["flow_namespace", "flow_name"],
                "name": "fk_by_source_tst_with_days_from_state",
            }
        }
    )

    flow_namespace: str
    flow_name: str
    last_pull_to_timestamp: datetime.datetime | None = None

    @field_validator("last_pull_to_timestamp", mode="before")
    @classmethod
    def normalize_utc_timezone(
        cls,
        value: datetime.datetime | None,
    ) -> datetime.datetime | None:
        return normalize_to_utc(value)


class BySourceTstWithDaysFromProcessingStateRow(NldBaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "functional_key": {
                "fields": ["flow_namespace", "flow_name"],
                "name": "fk_by_source_tst_with_days_from_processing_state",
            }
        }
    )

    flow_uid: str = Field(json_schema_extra={"primary_key": True})
    flow_namespace: str
    flow_name: str
    pull_from_timestamp: datetime.datetime | None = None
    pull_to_timestamp: datetime.datetime | None = None
    processing_status: str | None = None
    process_error_message: str | None = None
    processing_completed_at: datetime.datetime | None = None
    strategy: str

    @field_validator(
        "processing_completed_at",
        "pull_from_timestamp",
        "pull_to_timestamp",
        mode="before",
    )
    @classmethod
    def normalize_utc_timezone(
        cls,
        value: datetime.datetime | None,
    ) -> datetime.datetime | None:
        return normalize_to_utc(value)


class BySourceTstWithDaysFromPlannedProcessingStateRow(NldBaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "functional_key": {
                "fields": ["plan_state_uid"],
                "name": "fk_by_source_tst_with_days_from_planned_processing_state",
            },
        },
    )

    plan_state_uid: str = Field(json_schema_extra={"primary_key": True})
    flow_namespace: str
    flow_name: str
    pull_from_timestamp: datetime.datetime | None = None
    pull_to_timestamp: datetime.datetime | None = None
    strategy: str

    @field_validator("pull_from_timestamp", "pull_to_timestamp", mode="before")
    @classmethod
    def normalize_utc_timezone(
        cls,
        value: datetime.datetime | None,
    ) -> datetime.datetime | None:
        return normalize_to_utc(value)


class PostgreSQLBySourceTstWithDaysFromStateBackendManager(
    PostgreSQLIncrementalBackendMixin,
    BySourceTstWithDaysFromStateBackendManager[Psycopg2SQLConnector],
):
    param_definitions = []

    def __init__(
        self,
        backend_connector: Psycopg2SQLConnector,
        flow_namespace: str,
        flow_name: str,
        parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            backend_connector=backend_connector,
            flow_namespace=flow_namespace,
            flow_name=flow_name,
            parameters=parameters,
            **kwargs,
        )
        self.pydantic_manager = self.backend_connector.get_model_manager()
        self._ensure_tables_exist()
        self._ensure_planned_state_table_exists()

    def _ensure_tables_exist(self) -> None:
        self.pydantic_manager.create_table(
            model_class=BySourceTstWithDaysFromStateRow,
            schema_name=self.backend_schema_name,
            table_name=PSQL_STATE_TABLE_NAME,
            table_exists="skip",
            track_timestamps=True,
            use_functional_key_as_primary=True,
        )
        self.pydantic_manager.create_table(
            model_class=BySourceTstWithDaysFromProcessingStateRow,
            schema_name=self.backend_schema_name,
            table_name=PSQL_PROCESSING_STATE_TABLE_NAME,
            table_exists="skip",
            track_timestamps=True,
            use_functional_key_as_primary=False,
        )

    def read_processing_state(
        self,
    ) -> BySourceTstWithDaysFromProcessingState | None:
        row = cast(
            BySourceTstWithDaysFromProcessingStateRow | None,
            self.pydantic_manager.read_model(
                model_class=BySourceTstWithDaysFromProcessingStateRow,
                schema_name=self.backend_schema_name,
                table_name=PSQL_PROCESSING_STATE_TABLE_NAME,
                where_conditions={
                    "flow_namespace": self.flow_namespace,
                    "flow_name": self.flow_name,
                },
                order_by=["-processing_completed_at"],
            ),
        )
        if row is None:
            return None
        return BySourceTstWithDaysFromProcessingState(
            flow_uid=row.flow_uid,
            strategy=row.strategy,
            pull_from_timestamp=row.pull_from_timestamp,
            pull_to_timestamp=row.pull_to_timestamp,
            processing_status=row.processing_status or "",
            process_error_message=row.process_error_message,
            processing_completed_at=row.processing_completed_at,
        )

    def read_post_processing_state(self) -> BySourceTstWithDaysFromState | None:
        row = cast(
            BySourceTstWithDaysFromStateRow | None,
            self.pydantic_manager.read_model(
                model_class=BySourceTstWithDaysFromStateRow,
                schema_name=self.backend_schema_name,
                table_name=PSQL_STATE_TABLE_NAME,
                where_conditions={
                    "flow_namespace": self.flow_namespace,
                    "flow_name": self.flow_name,
                },
            ),
        )
        if row is None:
            return None
        return BySourceTstWithDaysFromState(
            last_pull_to_timestamp=row.last_pull_to_timestamp,
        )

    def read_current_state(self) -> BySourceTstWithDaysFromState:
        return self.read_post_processing_state() or BySourceTstWithDaysFromState()

    def write_processing_state(
        self,
        processing_flow_state: BySourceTstWithDaysFromProcessingState,
    ) -> None:
        row = BySourceTstWithDaysFromProcessingStateRow(
            flow_namespace=self.flow_namespace,
            flow_name=self.flow_name,
            flow_uid=processing_flow_state.flow_uid,
            process_error_message=processing_flow_state.process_error_message,
            processing_completed_at=processing_flow_state.processing_completed_at,
            processing_status=processing_flow_state.processing_status,
            pull_from_timestamp=processing_flow_state.pull_from_timestamp,
            pull_to_timestamp=processing_flow_state.pull_to_timestamp,
            strategy=processing_flow_state.strategy,
        )
        self.pydantic_manager.upsert_model(
            model=row,
            schema_name=self.backend_schema_name,
            table_name=PSQL_PROCESSING_STATE_TABLE_NAME,
            conflict_fields=["flow_uid"],
            commit=True,
            track_timestamps=True,
        )

    def write_post_processing_state(
        self,
        post_processing_flow_state: BySourceTstWithDaysFromState,
    ) -> None:
        row = BySourceTstWithDaysFromStateRow(
            flow_namespace=self.flow_namespace,
            flow_name=self.flow_name,
            last_pull_to_timestamp=post_processing_flow_state.last_pull_to_timestamp,
        )
        self.pydantic_manager.upsert_model(
            model=row,
            schema_name=self.backend_schema_name,
            table_name=PSQL_STATE_TABLE_NAME,
            conflict_fields=["flow_namespace", "flow_name"],
            commit=False,
            track_timestamps=True,
        )

    # ---- PostgreSQLIncrementalBackendMixin hooks ----

    def _ensure_planned_processing_state_table_exists(self) -> None:
        self.pydantic_manager.create_table(
            model_class=BySourceTstWithDaysFromPlannedProcessingStateRow,
            schema_name=self.backend_schema_name,
            table_name=PSQL_PLANNED_PROCESSING_STATE_TABLE_NAME,
            table_exists="skip",
            track_timestamps=True,
            use_functional_key_as_primary=True,
        )

    def write_planned_processing_state(
        self,
        plan_state_uid: str,
        detailed_state: BySourceTstWithDaysFromPlannedProcessingDetailedState,
    ) -> None:
        row = BySourceTstWithDaysFromPlannedProcessingStateRow(
            plan_state_uid=plan_state_uid,
            flow_namespace=self.flow_namespace,
            flow_name=self.flow_name,
            pull_from_timestamp=detailed_state.pull_from_timestamp,
            pull_to_timestamp=detailed_state.pull_to_timestamp,
            strategy=detailed_state.strategy,
        )
        self.pydantic_manager.upsert_model(
            model=row,
            schema_name=self.backend_schema_name,
            table_name=PSQL_PLANNED_PROCESSING_STATE_TABLE_NAME,
            conflict_fields=["plan_state_uid"],
            commit=True,
            track_timestamps=True,
        )

    def read_planned_processing_state(
        self,
        plan_state_uid: str,
    ) -> BySourceTstWithDaysFromPlannedProcessingDetailedState | None:
        rows = cast(
            list[BySourceTstWithDaysFromPlannedProcessingStateRow],
            self.pydantic_manager.read_models(
                model_class=BySourceTstWithDaysFromPlannedProcessingStateRow,
                schema_name=self.backend_schema_name,
                table_name=PSQL_PLANNED_PROCESSING_STATE_TABLE_NAME,
                where_conditions={"plan_state_uid": plan_state_uid},
            ),
        )
        if not rows:
            return None
        row = rows[0]
        return BySourceTstWithDaysFromPlannedProcessingDetailedState(
            plan_state_uid=row.plan_state_uid,
            strategy=row.strategy,
            pull_from_timestamp=row.pull_from_timestamp,
            pull_to_timestamp=row.pull_to_timestamp,
        )
