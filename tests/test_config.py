"""Environment overrides must not mutate the shared YAML configuration."""
def test_model_override_does_not_mutate_config(monkeypatch):
    from src.utils.config import get_config, get_llm_settings
    original = dict(get_config()["llm"])
    monkeypatch.setenv("QWEN_MODEL", "example-provider-model")
    assert get_llm_settings()["model"] == "example-provider-model"
    assert get_config()["llm"] == original
    monkeypatch.delenv("QWEN_MODEL")
    assert get_llm_settings() == original
