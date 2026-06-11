from importlib.metadata import PackageNotFoundError, version

from voxeye._redaction import Redaction
from voxeye._tracer import Observability

try:
    __version__ = version("voxeye")
except PackageNotFoundError:  # not installed (e.g. running from source tree)
    __version__ = "0.0.0"

__all__ = ["Observability", "Redaction", "__version__"]
