import unittest
import mock

from microproxy.server_state import init_server_state, _init_cert_store, _init_interceptor


class ServerStateAPITest(unittest.TestCase):
    def setUp(self):
        self.config = dict()

    @mock.patch("microproxy.server_state.ServerContext")
    @mock.patch("microproxy.server_state._init_cert_store")
    @mock.patch("microproxy.server_state._init_interceptor")
    def test_init_server_state(self,
                               mock_init_interceptor,
                               mock_init_cert_store,
                               MockServerContext):
        publish_socket = dict()
        context = init_server_state(self.config, publish_socket)

        mock_init_cert_store.assert_called_once_with(self.config)
        mock_init_interceptor.assert_called_once_with(
            self.config, publish_socket)

        MockServerContext.assert_called_once_with(
            config=self.config,
            interceptor=mock_init_interceptor.return_value,
            cert_store=mock_init_cert_store.return_value)
        self.assertEqual(context, MockServerContext.return_value)

    @mock.patch("microproxy.server_state.CertStore")
    def test_init_cert_store(self, MockCertStore):
        cert_store = _init_cert_store(self.config)

        MockCertStore.assert_called_once_with(self.config)
        self.assertEqual(cert_store, MockCertStore.return_value)

    @mock.patch("microproxy.server_state.MsgPublisher")
    @mock.patch("microproxy.server_state.PluginManager")
    @mock.patch("microproxy.server_state.Interceptor")
    def test_init_interceptor(self,
                              MockInterceptor,
                              MockPluginManager,
                              MockMsgPublisher):

        publish_socket = dict()
        interceptor = _init_interceptor(self.config, publish_socket)

        self.assertEqual(interceptor, MockInterceptor.return_value)

        MockPluginManager.assert_called_once_with(self.config)
        MockMsgPublisher.assert_called_once_with(
            self.config, zmq_socket=publish_socket)
        MockInterceptor.assert_called_once_with(
            plugin_manager=MockPluginManager.return_value,
            msg_publisher=MockMsgPublisher.return_value)
