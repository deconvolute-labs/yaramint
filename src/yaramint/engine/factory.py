from typing import Any

from yaramint.engine.base import BaseEngine
from yaramint.engine.ngram import NgramEngine
from yaramint.engine.stub import StubEngine
from yaramint.errors import ConfigurationError
from yaramint.models.engine_config import BaseEngineConfig


def get_engine(config: BaseEngineConfig) -> BaseEngine[BaseEngineConfig]:
    """
    Factory to instantiate the correct extraction strategy.

    Args:
        config: The configuration object (already cast to the correct subclass).

    Returns:
        An initialized instance of a BaseEngine subclass.

    Raises:
        ConfigurationError: If the engine type (config.type) is unknown.
    """
    engine_map: dict[str, type[BaseEngine[Any]]] = {
        "stub": StubEngine,
        "ngram": NgramEngine,
    }

    if config.type not in engine_map:
        valid_engines = ", ".join(engine_map.keys())
        raise ConfigurationError(
            f"Unknown engine type '{config.type}'. Available: {valid_engines}"
        )

    engine_class = engine_map[config.type]
    return engine_class(config)
