from api.chat.replay import replay_allowed
from fplcore.settings import Settings


def test_replay_is_refused_in_production_without_an_allow_list() -> None:
    settings = Settings(app_env="production", chat_admin_user_ids="")
    assert replay_allowed(settings) is False


def test_replay_is_allowed_in_development() -> None:
    settings = Settings(app_env="development", chat_admin_user_ids="")
    assert replay_allowed(settings) is True
