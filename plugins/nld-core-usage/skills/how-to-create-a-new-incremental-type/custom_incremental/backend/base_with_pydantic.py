"""Abstract backend for `by_source_tst_with_days_from`.

Concrete per-engine backends subclass this and override the read/write
methods inherited from ``IncrementalBackendStateManager``. The
``fallback_to_base_backend`` flag on the registered manifest (True by
default) lets the factory fall back here when no module is provided for
the requested ``(backend_type, engine)`` pair.
"""

import abc
from typing import Any

from nld.connector.base.connector import DataConnector
from nld.flow.incremental.base.manager import (
    IncrementalBackendStateManager,
)

from ..state import (
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
    ],
    abc.ABC,
):
    pass
