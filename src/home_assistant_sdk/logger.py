"""
Home Assistant SDK 日志管理模块

这个模块提供了统一的日志管理功能，支持：
- 日志等级配置
- 日志输出格式配置
- 多种输出形式（控制台、文件、或同时输出到两者）
- 文件输出路径配置
- 抽象的日志接口，方便未来切换到其他日志框架
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union
from enum import Enum


class LogLevel(str, Enum):
    """日志等级枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogOutput(str, Enum):
    """日志输出形式枚举"""
    CONSOLE = "console"          # 仅控制台
    FILE = "file"                # 仅文件
    BOTH = "both"                # 控制台和文件


class LoggerConfig:
    """日志配置类"""
    
    def __init__(
        self,
        level: Union[str, LogLevel] = LogLevel.INFO,
        output: Union[str, LogOutput] = LogOutput.CONSOLE,
        log_file: Optional[Union[str, Path]] = None,
        format_string: Optional[str] = None,
        date_format: Optional[str] = None,
        file_mode: str = "a",
        encoding: str = "utf-8",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        """
        初始化日志配置
        
        参数:
            level: 日志等级，可以是字符串或LogLevel枚举
            output: 输出形式，可以是字符串或LogOutput枚举
            log_file: 日志文件路径（当output为FILE或BOTH时必需）
            format_string: 日志格式字符串
            date_format: 日期格式字符串
            file_mode: 文件打开模式（'a'追加，'w'覆盖）
            encoding: 文件编码
            max_bytes: 单个日志文件最大大小（字节）
            backup_count: 保留的日志文件备份数量
        """
        self.level = level if isinstance(level, str) else level.value
        self.output = output if isinstance(output, str) else output.value
        self.log_file = Path(log_file) if log_file else None
        self.file_mode = file_mode
        self.encoding = encoding
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        
        # 默认日志格式：时间 - 日志器名称 - 等级 - 消息
        self.format_string = format_string or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        # 默认日期格式：年-月-日 时:分:秒
        self.date_format = date_format or "%Y-%m-%d %H:%M:%S"
        
        # 验证配置
        self._validate()
    
    def _validate(self):
        """验证配置参数的有效性"""
        # 验证输出形式
        if self.output in [LogOutput.FILE.value, LogOutput.BOTH.value]:
            if not self.log_file:
                raise ValueError(f"当输出形式为 '{self.output}' 时，必须指定 log_file 参数")
            
            # 确保日志目录存在
            if self.log_file:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)


class LoggerManager:
    """
    日志管理器
    
    提供统一的日志管理功能，支持：
    - 创建和配置logger
    - 多种输出形式
    - 抽象的日志接口
    """
    
    # 全局默认配置
    _default_config: Optional[LoggerConfig] = None
    # 已创建的logger缓存
    _loggers: dict[str, logging.Logger] = {}
    
    @classmethod
    def set_default_config(cls, config: LoggerConfig) -> None:
        """
        设置全局默认日志配置，并重新配置所有已存在的logger
        
        参数:
            config: 日志配置对象
        """
        cls._default_config = config
        
        # 重新配置所有已存在的logger
        for logger_name, logger in list(cls._loggers.items()):
            # 清除现有的handlers
            logger.handlers.clear()
            logger.setLevel(getattr(logging, config.level))
            
            # 创建formatter
            formatter = logging.Formatter(
                fmt=config.format_string,
                datefmt=config.date_format
            )
            
            # 根据输出形式添加handler
            if config.output in [LogOutput.CONSOLE.value, LogOutput.BOTH.value]:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
            
            if config.output in [LogOutput.FILE.value, LogOutput.BOTH.value]:
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    filename=str(config.log_file),
                    mode=config.file_mode,
                    maxBytes=config.max_bytes,
                    backupCount=config.backup_count,
                    encoding=config.encoding
                )
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
    
    @classmethod
    def get_logger(
        cls,
        name: str,
        config: Optional[LoggerConfig] = None
    ) -> logging.Logger:
        """
        获取或创建logger实例
        
        参数:
            name: logger名称，通常使用模块名 __name__
            config: 日志配置，如果为None则使用全局默认配置
            
        返回:
            logging.Logger: 配置好的logger实例
        """
        # 使用提供的配置或全局默认配置
        cfg = config or cls._default_config or LoggerConfig()
        
        # 如果logger已存在，直接返回（避免重复配置）
        if name in cls._loggers:
            return cls._loggers[name]
        
        # 创建logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, cfg.level))
        logger.handlers.clear()  # 清除已有的handler
        
        # 创建formatter
        formatter = logging.Formatter(
            fmt=cfg.format_string,
            datefmt=cfg.date_format
        )
        
        # 根据输出形式添加handler
        if cfg.output in [LogOutput.CONSOLE.value, LogOutput.BOTH.value]:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        if cfg.output in [LogOutput.FILE.value, LogOutput.BOTH.value]:
            # 使用RotatingFileHandler支持日志轮转
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                filename=str(cfg.log_file),
                mode=cfg.file_mode,
                maxBytes=cfg.max_bytes,
                backupCount=cfg.backup_count,
                encoding=cfg.encoding
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        # 缓存logger
        cls._loggers[name] = logger
        
        return logger
    
    @classmethod
    def configure_root_logger(cls, config: LoggerConfig) -> None:
        """
        配置根logger（影响所有未配置的logger）
        
        参数:
            config: 日志配置对象
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.level))
        root_logger.handlers.clear()
        
        formatter = logging.Formatter(
            fmt=config.format_string,
            datefmt=config.date_format
        )
        
        if config.output in [LogOutput.CONSOLE.value, LogOutput.BOTH.value]:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        if config.output in [LogOutput.FILE.value, LogOutput.BOTH.value]:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                filename=str(config.log_file),
                mode=config.file_mode,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding=config.encoding
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)


# ============ 抽象的日志接口 ============
class AbstractLogger:
    """
    抽象的日志接口
    
    这个类封装了标准库logging的API，方便未来切换到其他日志框架
    （例如：loguru, structlog等）而不需要修改业务代码
    """
    
    def __init__(self, logger: logging.Logger):
        """
        初始化抽象logger
        
        参数:
            logger: 标准库logging.Logger实例
        """
        self._logger = logger
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """记录DEBUG级别日志"""
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """记录INFO级别日志"""
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """记录WARNING级别日志"""
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """记录ERROR级别日志"""
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """记录CRITICAL级别日志"""
        self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, exc_info=True, **kwargs) -> None:
        """记录异常信息（包含堆栈跟踪）"""
        self._logger.exception(msg, *args, exc_info=exc_info, **kwargs)


# ============ 便捷函数 ============
def get_logger(
    name: str,
    level: Optional[Union[str, LogLevel]] = None,
    output: Optional[Union[str, LogOutput]] = None,
    log_file: Optional[Union[str, Path]] = None
) -> AbstractLogger:
    """
    获取logger的便捷函数
    
    参数:
        name: logger名称，通常使用模块名 __name__
        level: 日志等级（可选，使用全局默认配置）
        output: 输出形式（可选，使用全局默认配置）
        log_file: 日志文件路径（可选，使用全局默认配置）
        
    返回:
        AbstractLogger: 抽象logger实例
        
    示例:
        # 使用全局默认配置
        logger = get_logger(__name__)
        
        # 自定义配置
        logger = get_logger(__name__, level=LogLevel.DEBUG, output=LogOutput.BOTH, log_file="app.log")
    """
    # 如果提供了任何参数，创建自定义配置
    if any([level, output, log_file]):
        config = LoggerConfig(
            level=level or LogLevel.INFO,
            output=output or LogOutput.CONSOLE,
            log_file=log_file
        )
        std_logger = LoggerManager.get_logger(name, config)
    else:
        # 使用全局默认配置
        std_logger = LoggerManager.get_logger(name)
    
    return AbstractLogger(std_logger)


def setup_logging(
    level: Union[str, LogLevel] = LogLevel.INFO,
    output: Union[str, LogOutput] = LogOutput.CONSOLE,
    log_file: Optional[Union[str, Path]] = None,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None
) -> None:
    """
    设置全局日志配置的便捷函数
    
    参数:
        level: 日志等级
        output: 输出形式
        log_file: 日志文件路径
        format_string: 日志格式字符串
        date_format: 日期格式字符串
        
    示例:
        # 仅控制台输出
        setup_logging(level=LogLevel.INFO, output=LogOutput.CONSOLE)
        
        # 输出到文件
        setup_logging(level=LogLevel.DEBUG, output=LogOutput.FILE, log_file="app.log")
        
        # 同时输出到控制台和文件
        setup_logging(level=LogLevel.INFO, output=LogOutput.BOTH, log_file="app.log")
    """
    config = LoggerConfig(
        level=level,
        output=output,
        log_file=log_file,
        format_string=format_string,
        date_format=date_format
    )
    LoggerManager.set_default_config(config)


# ============ 使用示例 ============
if __name__ == "__main__":
    # 示例1: 使用全局默认配置（仅控制台）
    print("=== 示例1: 默认配置（仅控制台）===")
    setup_logging(level=LogLevel.INFO)
    logger1 = get_logger(__name__)
    logger1.debug("这条DEBUG消息不会显示")
    logger1.info("这是一条INFO消息")
    logger1.warning("这是一条WARNING消息")
    logger1.error("这是一条ERROR消息")
    
    # 示例2: 输出到文件
    print("\n=== 示例2: 输出到文件 ===")
    setup_logging(
        level=LogLevel.DEBUG,
        output=LogOutput.FILE,
        log_file="./logs/test.log"
    )
    logger2 = get_logger(__name__)
    logger2.debug("这条消息将写入文件")
    logger2.info("文件路径: ./logs/test.log")
    print("日志已写入文件: ./logs/test.log")
    
    # 示例3: 同时输出到控制台和文件
    print("\n=== 示例3: 同时输出到控制台和文件 ===")
    setup_logging(
        level=LogLevel.DEBUG,
        output=LogOutput.BOTH,
        log_file="./logs/both.log"
    )
    logger3 = get_logger(__name__)
    logger3.debug("这条消息会同时显示在控制台和文件中")
    logger3.info("双重输出测试成功")
    
    # 示例4: 自定义格式
    print("\n=== 示例4: 自定义格式 ===")
    setup_logging(
        level=LogLevel.INFO,
        output=LogOutput.CONSOLE,
        format_string="[%(levelname)s] %(name)s: %(message)s"
    )
    logger4 = get_logger(__name__)
    logger4.info("这是自定义格式的日志")
    
    # 示例5: 记录异常
    print("\n=== 示例5: 记录异常 ===")
    logger5 = get_logger(__name__)
    try:
        1 / 0
    except ZeroDivisionError:
        logger5.exception("捕获到异常")
    
    print("\n所有示例执行完成！")
