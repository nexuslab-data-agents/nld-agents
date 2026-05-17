"""PostgreSQL backend for `by_source_tst_with_days_from`.

Persists state and processing-state rows via the
``Psycopg2SQLConnector.pydantic_manager``. Mirrors the built-in
``PostgreSQLBySourceTstStateBackendManager`` — the watermark schema is
unchanged, so the row models are structurally identical and only the
table names differ.
"""

import datetime
from typing import Any, cast

from pydantic import ConfigDict, Field, field_validator

from nld.connector.postgresql.engine.psycopg2.connector import (
    Psycopg2SQLConnector,
)
from nld.flow.backend.postgresql.backend_mixin import PostgreSQLBackendMixin
from nld.flow.backend.postgresql.utils import PSQL_BACKEND_INCREMENTAL_TABLE_PREFIX
from nld.pydantic import NldBaseModel
from nld.utils.datetime_util import normalize_to_utc

from ..state import (
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


class PostgreSQLBySourceTstWithDaysFromStateBackendManager(
    PostgreSQLBackendMixin,
    BySourceTstWithDaysFromStateBackendManager[Psycopg2SQLConnector],
):
    backend_param_definitions = []
    flow_param_definitions = []

    def __init__(
        self,
        backend_connector: Psycopg2SQLConnector,
        flow_namespace: str,
        flow_name: str,
        backend_parameters: dict[str, Any] | None = None,
        flow_parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            backend_connector=backend_connector,
            flow_namespace=flow_namespace,
            flow_name=flow_name,
            backend_parameters=backend_parameters,
            flow_parameters=flow_parameters,
            **kwargs,
        )
        self.pydantic_manager = self.backend_connector.get_model_manager()
        self._ensure_tables_exist()

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

    def get_processing_state(
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

    def get_post_processing_state(self) -> BySourceTstWithDaysFromState | None:
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

    def retrieve_current_state(self) -> BySourceTstWithDaysFromState:
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
            return BySourceTstWithDaysFromState()
        return BySourceTstWithDaysFromState(
            last_pull_to_timestamp=row.last_pull_to_timestamp,
        )

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
