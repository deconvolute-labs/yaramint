from yaramint.engine.factory import get_engine
from yaramint.engine.ngram import NgramEngine
from yaramint.engine.stub import StubEngine
from yaramint.models.engine_config import BaseEngineConfig, NgramEngineConfig


class TestEngineFactory:
    def test_get_stub_engine(self):
        """Test retrieving the Stub engine."""
        config = BaseEngineConfig(type="stub")
        engine = get_engine(config)

        assert isinstance(engine, StubEngine)
        # Ensure config was passed down
        assert engine.config == config

    def test_get_ngram_engine(self):
        """Test retrieving the N-Gram engine."""
        config = NgramEngineConfig(min_ngram=2)
        engine = get_engine(config)

        assert isinstance(engine, NgramEngine)
        assert engine.config.min_ngram == 2
