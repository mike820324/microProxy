import logging
import logging.config
from zmq.log.handlers import PUBHandler


class ProxyLogger(object):
    formatter = logging.Formatter("%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s")

    @classmethod
    def init_proxy_logger(cls, config):
        if config["logger_config"]:
            # NOTE: If user specify the logging config file,
            # used it to configure the logger behavior.
            # Moreover, the disable_existing_loggers is necessary,
            # since most of our code will get logger before we initialize it.
            logging.config.fileConfig(config["logger_config"], disable_existing_loggers=False)
        else:
            # NOTE: Otherwise, we start setup the logger based on other configure value.
            logger = logging.getLogger()
            log_level = getattr(logging, config["log_level"].upper())
            logger.setLevel(log_level)

            if config["log_file"]:
                cls.register_file_handler(config["log_file"])
            else:
                cls.register_stream_handler()

    @classmethod
    def register_zmq_handler(cls, zmq_socket):  # pragma: no cover
        handler = PUBHandler(zmq_socket)
        handler.root_topic = "logger"

        logger = logging.getLogger()
        logger.addHandler(handler)

    @classmethod
    def register_file_handler(cls, filename):  # pragma: no cover
        fileHandler = logging.FileHandler(filename, encoding="utf8")
        fileHandler.setFormatter(cls.formatter)

        logger = logging.getLogger()
        logger.addHandler(fileHandler)

    @classmethod
    def register_stream_handler(cls):  # pragma: no cover
        basicHandler = logging.StreamHandler()
        basicHandler.setFormatter(cls.formatter)

        logger = logging.getLogger()
        logger.addHandler(basicHandler)

    @classmethod
    def get_logger(cls, name):  # pragma: no cover
        logger = logging.getLogger(name)
        return logger
