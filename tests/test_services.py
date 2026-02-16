import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from agentic_cli.services.base import Service


class TestServiceBase:
    def test_service_is_abstract(self):
        with pytest.raises(TypeError):
            Service()

    def test_service_has_name_property(self):
        class TestService(Service):
            @property
            def name(self):
                return "test"

            def initialize(self):
                return True

            def shutdown(self):
                pass

        service = TestService()
        assert service.name == "test"

    def test_service_has_initialize(self):
        class TestService(Service):
            @property
            def name(self):
                return "test"

            def initialize(self):
                return True

            def shutdown(self):
                pass

        service = TestService()
        assert service.initialize() is True

    def test_service_has_shutdown(self):
        class TestService(Service):
            @property
            def name(self):
                return "test"

            def initialize(self):
                return True

            def shutdown(self):
                pass

        service = TestService()
        service.shutdown()
