from fplcore.explain.llm import LLMExplainer
from fplcore.explain.protocol import Explainer
from fplcore.explain.template import TemplateExplainer
from fplcore.settings import Settings, get_settings


def get_explainer(settings: Settings | None = None) -> Explainer:
    cfg = settings or get_settings()
    if cfg.llm_api_key and cfg.llm_model:
        return LLMExplainer(cfg)
    return TemplateExplainer()
