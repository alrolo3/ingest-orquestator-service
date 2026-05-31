import pytest

from ingest_orquestator_server.config import Settings


@pytest.fixture(autouse=True)
def disable_implicit_dotenv_for_tests():
    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    yield
    Settings.model_config["env_file"] = original_env_file
