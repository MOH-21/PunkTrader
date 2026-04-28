import pytest


@pytest.fixture(scope="session")
def flask_app():
    import app as flask_module
    flask_module.app.config["TESTING"] = True
    return flask_module.app


@pytest.fixture
def client(flask_app):
    with flask_app.test_client() as c:
        yield c
