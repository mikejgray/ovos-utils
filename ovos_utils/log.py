# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import functools
import inspect
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from os.path import join
from pathlib import Path
from typing import Optional, List, Set

ALL_SERVICES = {"bus",
                "audio",
                "skills",
                "voice",
                "gui",
                "ovos",
                "phal",
                "phal-admin",
                "hivemind",
                "hivemind-voice-sat"}


class LOG:
    """
    Custom logger class that acts like logging.Logger

    The logger name is gnerally set by the calling module, but the default name
    is read from the envvar `OVOS_DEFAULT_LOG_NAME`.

    The log level defaults to `INFO` and can be overridden by
    `OVOS_DEFAULT_LOG_LEVEL`. Note that log level may be overridden by
     configuration when calling `LOG.init`.

    The config file can have a "logging" section

    {
        "logging": {
	    "log_level": "INFO",  // default log level
            "logs": {
                "path": "/opt/ovos/logs/",
                "max_bytes": 50000000,
                "backup_count": 6
            }.
            "bus": {  // override for different services
	        "log_level": "DEBUG"
                "logs": { // optionally override default logs
                          // (nb this does not merge values so
                          // backup_count takes the default 3 here)
                      "path": "/path/for/just/bus/logs"
                }
	     },
        },
        ....
    }


    Usage:
        >>> LOG.debug('My message: %s', debug_str)
        13:12:43.673 - :<module>:1 - DEBUG - My message: hi
        >>> LOG('custom_name').debug('Another message')
        13:13:10.462 - custom_name - DEBUG - Another message
    """
    base_path = "stdout"
    fmt = '%(asctime)s.%(msecs)03d - ' \
          '%(name)s - %(levelname)s - %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(fmt, datefmt)
    max_bytes = 50000000
    backup_count = 3
    name = os.getenv("OVOS_DEFAULT_LOG_NAME") or "OVOS"
    level = os.getenv("OVOS_DEFAULT_LOG_LEVEL") or "INFO"
    diagnostic_mode = False
    _loggers = {}

    @classmethod
    def __init__(cls, name=name):
        cls.name = name

    @classmethod
    def init(cls, config=None):
        from ovos_utils.xdg_utils import xdg_state_home
        try:
            from ovos_config.meta import get_xdg_base
            xdg_base = get_xdg_base()
        except ImportError:
            xdg_base = os.environ.get("OVOS_CONFIG_BASE_FOLDER") or "mycroft"

        xdg_path = os.path.join(xdg_state_home(), xdg_base)

        config = config or {}
        cls.base_path = config.get("path") or xdg_path
        cls.max_bytes = config.get("max_bytes", 50000000)
        cls.backup_count = config.get("backup_count", 3)
        cls.level = config.get("level") or LOG.level
        cls.diagnostic_mode = config.get("diagnostic", False)

    @classmethod
    def create_logger(cls, name, tostdout=True):
        if name in cls._loggers:
            return cls._loggers[name]
        logger = logging.getLogger(name)
        logger.propagate = False
        # also log to stdout
        if tostdout or cls.base_path == "stdout":
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(cls.formatter)
            logger.addHandler(stdout_handler)
        # log to file
        if cls.base_path != "stdout":
            os.makedirs(cls.base_path, exist_ok=True)
            path = join(cls.base_path,
                        cls.name.lower().strip() + ".log")
            handler = RotatingFileHandler(path, maxBytes=cls.max_bytes,
                                          backupCount=cls.backup_count)
            handler.setFormatter(cls.formatter)
            logger.addHandler(handler)
        logger.setLevel(cls.level)
        cls._loggers[name] = logger
        return logger

    @classmethod
    def set_level(cls, level):
        cls.level = level
        for l in cls._loggers:
            cls._loggers[l].setLevel(level)

    @classmethod
    def _get_real_logger(cls):
        name = ""
        if cls.name is not None:
            name = cls.name + " - "

        # Stack:
        # [0] - _log()
        # [1] - debug(), info(), warning(), or error()
        # [2] - caller
        stack = inspect.stack()

        # Record:
        # [0] - frame object
        # [1] - filename
        # [2] - line number
        # [3] - function
        # ...
        record = stack[2]
        mod = inspect.getmodule(record[0])
        module_name = mod.__name__ if mod else ''
        name += module_name + ':' + record[3] + ':' + str(record[2])

        logger = cls.create_logger(name, tostdout=True)
        if cls.diagnostic_mode:
            try:
                from ovos_bus_client.message import dig_for_message
                msg = dig_for_message()
                if msg:
                    logger.debug(f"DIAGNOSTIC - source bus message {msg.serialize()}")
            except ImportError:
                pass
        return logger

    @classmethod
    def info(cls, *args, **kwargs):
        cls._get_real_logger().info(*args, **kwargs)

    @classmethod
    def debug(cls, *args, **kwargs):
        cls._get_real_logger().debug(*args, **kwargs)

    @classmethod
    def warning(cls, *args, **kwargs):
        cls._get_real_logger().warning(*args, **kwargs)

    @classmethod
    def error(cls, *args, **kwargs):
        cls._get_real_logger().error(*args, **kwargs)

    @classmethod
    def exception(cls, *args, **kwargs):
        cls._get_real_logger().exception(*args, **kwargs)


def init_service_logger(service_name):
    # this is makes all logs from this service be configured to write to service_name.log file
    # if this is not called in every __main__.py entrypoint logs will be written
    # to a generic OVOS.log file shared across all services
    try:
        from ovos_config.config import read_mycroft_config
        _cfg = read_mycroft_config()
    except ImportError:
        LOG.warning("ovos_config not available. Falling back to defaults")
        _cfg = dict()

    # First try and get the "logging" section
    log_config = _cfg.get("logging")
    # For compatibility we try to get the "logs" from the root level
    # and default to empty which is used in case there is no logging
    # section
    _logs_conf = _cfg.get("logs") or {}
    if log_config:  # We found a logging section
        # if "logs" is defined in "logging" use that as the default
        # where per-service "logs" are not defined
        _logs_conf = log_config.get("logs") or _logs_conf
        # Now get our config by service name
        _cfg = log_config.get(service_name) or log_config
        # and if "logs" is redefined in "logging.<service_name>" use that
        _logs_conf = _cfg.get("logs") or _logs_conf
    # Grab the log level from whatever section we found, defaulting to INFO
    _log_level = _cfg.get("log_level", "INFO")
    # and write it into the "logs" config
    _logs_conf["level"] = _log_level
    LOG.name = service_name
    LOG.init(_logs_conf)  # setup the LOG instance


def log_deprecation(log_message: str = "DEPRECATED",
                    deprecation_version: str = "Unknown",
                    func_name: str = "",
                    func_module: str = "",
                    excluded_package_refs: List[str] = [""]):
    """
    Log a deprecation warning with information for the call outside the module
    that is generating the warning
    @param log_message: Log contents describing the deprecation
    @param deprecation_version: package version in which method will be deprecated
    @param func_name: decorated function name (else read from stack)
    @param func_module: decorated function module (else read from stack)
    @param excluded_package_refs: list of packages to exclude from call origin
        determination. i.e. an internal exception handling method should log the
        first call external to that package
    """
    stack = inspect.stack()[1:]  # [0] is this method
    call_info = "Unknown Origin"
    origin_module = func_module
    log_name = f"{LOG.name} - {func_module}:{func_name}" if \
        func_module and func_name else LOG.name
    for call in stack:
        module = inspect.getmodule(call.frame)
        name = module.__name__ if module else call.filename
        if any((name if name.startswith(x) else None
                for x in ("ovos_utils.log", "<"))):
            # Skip calls from this module and unittests to get at real origin
            continue
        if not origin_module:
            # Assume first outside call is the origin if not specified
            origin_module = name
            log_name = f"{LOG.name} - {name}:{func_name or call[3]}:{call[2]}"
            continue
        if excluded_package_refs and any((name.startswith(x) for x in
                                          excluded_package_refs)):
            continue
        if not name.startswith(origin_module):
            call_info = f"{name}:{call.lineno}"
            break
    # Explicitly format log to print origin log reference
    LOG.create_logger(log_name).warning(
        f"Deprecation version={deprecation_version}. Caller={call_info}. "
        f"{log_message}")


def deprecated(log_message: str, deprecation_version: str):
    """
    Decorator to log deprecation on call to deprecated function
    @param log_message: Deprecation log message
    @param deprecation_version: package version in which deprecation will occur
    """

    def wrapped(func):
        @functools.wraps(func)
        def log_wrapper(*args, **kwargs):
            log_deprecation(log_message=log_message,
                            func_name=func.__qualname__,
                            func_module=func.__module__,
                            deprecation_version=deprecation_version)
            return func(*args, **kwargs)

        return log_wrapper

    return wrapped


def get_log_path(service: str, directories: Optional[List[str]] = None) \
        -> Optional[str]:
    """
    Get the path to the log directory for a given service.
    Default behaviour is to check the configured paths for the service.
    If a list of directories is provided, check that list for the service log

    Args:
        service: service name
        directories: (optional) list of directories to check for service

    Returns:
        path to log directory for service
    """
    if directories:
        for directory in directories:
            file = os.path.join(directory, f"{service}.log")
            if os.path.exists(file):
                return directory
        return None

    from ovos_utils.xdg_utils import xdg_state_home
    try:
        from ovos_config import Configuration
        from ovos_config.meta import get_xdg_base
    except ImportError:
        xdg_base = os.environ.get("OVOS_CONFIG_BASE_FOLDER", "mycroft")
        return os.path.join(xdg_state_home(), xdg_base)

    config = Configuration().get("logging", dict()).get("logs", dict())
    # service specific config or default config location
    path = config.get(service, {}).get("path") or config.get("path")
    # default xdg location
    if not path:
        path = os.path.join(xdg_state_home(), get_xdg_base())

    return path


def get_log_paths() -> Set[str]:
    """
    Get all log paths for all service logs
    Different services may have different log paths

    Returns:
        set of paths to log directories
    """
    paths = set()
    ALL_SERVICES.union({s.replace("-", "_") for s in ALL_SERVICES})
    for service in ALL_SERVICES:
        paths.add(get_log_path(service))

    return paths


def get_available_logs(directories: Optional[List[str]] = None) -> List[str]:
    """
    Get a list of all available log files
    Args:
        directories: (optional) list of directories to check for service

    Returns:
        list of log files
    """
    directories = directories or list(get_log_paths())
    return [Path(f).stem for path in directories
            for f in os.listdir(path) if Path(f).suffix == ".log"]
