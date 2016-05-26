import os
import sys
from copy import copy
from watchdog.events import RegexMatchingEventHandler
from microproxy.utils import get_logger

if sys.platform == "darwin":
    from watchdog.observers.polling import PollingObserver as Observer
else:
    from watchdog.observers import Observer

logger = get_logger(__name__)


class PluginEventHandler(RegexMatchingEventHandler):
    def __init__(self, filename, callback):
        super(PluginEventHandler, self).__init__(ignore_directories=True,
                                                 regexes=['.*' + filename])
        self.callback = callback

    def on_modified(self, event):
        self.callback()


class Plugin(object):
    PLUGIN_METHODS = ["on_request", "on_response"]

    def __init__(self, plugin_path):
        self.plugin_path = os.path.abspath(plugin_path)
        self.plugin_name = os.path.basename(self.plugin_path)
        self.plugin_dir = os.path.dirname(self.plugin_path)
        self.namespace = None
        self._load_plugin()
        self._register_watcher()

    def _register_watcher(self):
        logger.debug("Register File Watcher for {0}".format(self.plugin_name))
        self.event_handler = PluginEventHandler(self.plugin_name,
                                                self._reload_plugin)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.plugin_dir)
        self.observer.start()

    def _load_plugin(self):
        sys.path.append(os.path.dirname(self.plugin_path))
        try:
            with open(self.plugin_path) as fp:
                self.namespace = {"__file__": self.plugin_path}
                code = compile(fp.read(), self.plugin_path, "exec")
                exec (code, self.namespace, self.namespace)

        except Exception as e:
            logger.exception(e)

        sys.path.pop()
        logger.info("Load Plugin : {0}".format(self.plugin_name))

    def _reload_plugin(self):
        logger.info("Reload Plugin : {0}".format(self.plugin_name))
        self._load_plugin()

    def __getattr__(self, attr):
        if attr not in self.PLUGIN_METHODS:
            raise AttributeError
        try:
            return self.namespace[attr]
        except KeyError:
            raise AttributeError


class PluginManager(object):
    def __init__(self, config):
        self.plugins = []
        self.load_plugins(config["plugins"])

    def load_plugins(self, plugin_paths):
        for plugin_path in plugin_paths:
            plugin = Plugin(plugin_path)
            self.plugins.append(plugin)

    def exec_request(self, request):
        if len(self.plugins) == 0:
            return request

        current_request = copy(request)
        for plugin in self.plugins:
            try:
                new_request = plugin.on_request(current_request)
                current_request = copy(new_request)
            except AttributeError:
                logger.debug("Plugin {0} does not have on_request".format(plugin.namespace["__file__"].split("/")[-1]))
        return current_request

    def exec_response(self, response):
        if len(self.plugins) == 0:
            return response

        current_response = copy(response)
        for plugin in self.plugins:
            try:
                new_response = plugin.on_response(current_response)
                current_response = copy(new_response)
            except AttributeError:
                logger.debug("Plugin {0} does not have on_response".format(plugin.namespace["__file__"].split("/")[-1]))
        return current_response
