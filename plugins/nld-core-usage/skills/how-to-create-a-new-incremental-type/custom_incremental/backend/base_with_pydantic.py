"""Abstract backend for `by_source_tst_with_days_from`.

Concrete per-backend modules subclass this and implement the read/write
methods of ``IncrementalBackendStateManager``. The
``fallback_to_base_backend`` flag on the registered manifest (True by
default) lets the factory fall back here when no module is provided for
the requested ``(backend_type, engine)`` pair; the factory then rejects
the class because it is abstract.
"""

import abc
from typing import Any

from nld.connector.base.connector import DataConnector
from nld.flow.incremental.base.manager import IncrementalBackendStateManager

from ..state import (
    BySourceTstWithDaysFromPlannedProcessingDetailedState,
    BySourceTstWithDaysFromPlannedProcessingState,
    BySourceTstWithDaysFromProcessingState,
    BySourceTstWithDaysFromSourceState,
    BySourceTstWithDaysFromState,
)


class BySourceTstWithDaysFromStateBackendManager[
    DATA_CONNECTOR: DataConnector[Any]
](
    IncrementalBackendStateManager[
        DATA_CONNECTOR,
        BySourceTstWithDaysFromState,
        BySourceTstWithDaysFromSourceState,
        BySourceTstWithDaysFromProcessingState,
        BySourceTstWithDaysFromPlannedProcessingState,
        BySourceTstWithDaysFromPlannedProcessingDetailedState,
    ],
    abc.ABC,
):
    pass
