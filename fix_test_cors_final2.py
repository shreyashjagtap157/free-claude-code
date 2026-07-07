from fastapi.testclient import TestClient
from api.app import create_app
from config.settings import NimSettings

# Since get_settings uses lru_cache, and the test uses patch, maybe the app itself resolves settings internally not through our mocked return_value if it's already cached? Wait, `create_app` calls `get_settings()`.
# Wait! In test_cors_host.py:
# `app = create_app(lifespan_enabled=False)`
# Let's write a script that runs EXACTLY the test.
