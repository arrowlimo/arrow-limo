"""
DEPRECATED MODULE
-----------------
This file previously contained a duplicate Flask API implementation.
All API code now lives in the top-level module `api.py` to avoid confusion.

This shim is kept only for backward compatibility with any references like
`new_system.api:app` in process managers or scripts. It forwards `app` from the
root `api` module and warns at import/run time.
"""

from __future__ import annotations

import os
import warnings
import importlib

warnings.warn(
    "new_system.api is deprecated; use top-level 'api.py' (module name 'api') instead.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    _root_api = importlib.import_module('api')
    # Expose the Flask app so references like `new_system.api:app` continue to work
    app = getattr(_root_api, 'app')  # type: ignore[attr-defined]
except Exception as _e:  # pragma: no cover - defensive
    raise ImportError(
        "Could not import top-level 'api'. Please run or point your server to 'api.py'."
    ) from _e


if __name__ == '__main__':  # pragma: no cover - manual run convenience
    print("[DEPRECATION] new_system.api is deprecated; starting top-level api.app instead...")
    port = int(os.environ.get('PORT', '5000'))
    # Run the forwarded app
    app.run(host='0.0.0.0', port=port)
