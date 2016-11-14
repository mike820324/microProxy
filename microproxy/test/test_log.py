import unittest
from mock import patch

from microproxy.log import ProxyLogger


class TestProxyLogger(unittest.TestCase):
    @patch('microproxy.log.ProxyLogger.register_stream_handler')
    @patch('microproxy.log.ProxyLogger.register_file_handler')
    @patch('logging.config.fileConfig')
    def test_init_proxy_logger_file_handler(self,
                                            mock_logging_fileConfig,
                                            mock_register_file_handler,
                                            mock_register_stream_handler):
        config = {
            "logger_config": "test.cfg",
            "log_file": "test.log",
            "log_level": "INFO"
        }
        ProxyLogger.init_proxy_logger(config)
        mock_logging_fileConfig.assert_called_once_with(filename="test.cfg", encoding="utf8")
        mock_register_file_handler.assert_not_called()
        mock_register_stream_handler.assert_not_called()

    @patch('microproxy.log.ProxyLogger.register_stream_handler')
    @patch('microproxy.log.ProxyLogger.register_file_handler')
    def test_init_proxy_logger_file_handler(self, mock_register_file_handler, mock_register_stream_handler):
        config = {
            "logger_config": "",
            "log_file": "test.log",
            "log_level": "INFO"
        }
        ProxyLogger.init_proxy_logger(config)
        mock_register_file_handler.assert_called_once_with("test.log")
        mock_register_stream_handler.assert_not_called()

    @patch('microproxy.log.ProxyLogger.register_stream_handler')
    @patch('microproxy.log.ProxyLogger.register_file_handler')
    def test_init_proxy_logger_stream_handler(self, mock_register_file_handler, mock_register_stream_handler):
        config = {
            "logger_config": "",
            "log_file": "",
            "log_level": "INFO"
        }
        ProxyLogger.init_proxy_logger(config)
        mock_register_stream_handler.assert_called_once()
        mock_register_file_handler.assert_not_called()
