# 日志管理模块使用指南

本项目已将所有 `print` 语句（除了 `if __name__ == "__main__"` 部分）替换为统一的日志管理模块。

## 模块概述

日志管理模块 (`logger.py`) 提供了：
- ✅ 统一的日志等级控制
- ✅ 灵活的输出形式（控制台、文件、或同时输出）
- ✅ 可配置的日志格式
- ✅ 文件日志轮转支持
- ✅ 抽象的日志接口（方便未来切换到其他日志框架）

## 快速开始

### 1. 基础使用（使用默认配置）

```python
from home_assistant_sdk import get_logger

# 创建logger
logger = get_logger(__name__)

# 使用logger记录日志
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
```

### 2. 配置全局日志设置

```python
from home_assistant_sdk import setup_logging, LogLevel, LogOutput

# 仅输出到控制台（默认）
setup_logging(level=LogLevel.INFO, output=LogOutput.CONSOLE)

# 仅输出到文件
setup_logging(
    level=LogLevel.DEBUG,
    output=LogOutput.FILE,
    log_file="./logs/app.log"
)

# 同时输出到控制台和文件
setup_logging(
    level=LogLevel.INFO,
    output=LogOutput.BOTH,
    log_file="./logs/app.log"
)
```

### 3. 自定义日志格式

```python
from home_assistant_sdk import setup_logging, LogLevel, LogOutput

setup_logging(
    level=LogLevel.DEBUG,
    output=LogOutput.BOTH,
    log_file="./logs/custom.log",
    format_string="[%(levelname)s] %(asctime)s - %(name)s: %(message)s",
    date_format="%Y-%m-%d %H:%M:%S"
)
```

## 日志等级说明

```python
from home_assistant_sdk import LogLevel

# 可用的日志等级（从低到高）：
LogLevel.DEBUG      # 调试信息
LogLevel.INFO       # 一般信息
LogLevel.WARNING    # 警告信息
LogLevel.ERROR      # 错误信息
LogLevel.CRITICAL   # 严重错误
```

## 输出形式说明

```python
from home_assistant_sdk import LogOutput

LogOutput.CONSOLE   # 仅输出到控制台
LogOutput.FILE      # 仅输出到文件
LogOutput.BOTH      # 同时输出到控制台和文件
```

## 完整示例

### 示例 1：开发环境配置

```python
from home_assistant_sdk import setup_logging, get_logger, LogLevel, LogOutput

# 开发环境：DEBUG级别，同时输出到控制台和文件
setup_logging(
    level=LogLevel.DEBUG,
    output=LogOutput.BOTH,
    log_file="./logs/dev.log"
)

logger = get_logger(__name__)
logger.debug("调试信息：变量值 = %s", some_var)
logger.info("应用程序启动成功")
```

### 示例 2：生产环境配置

```python
from home_assistant_sdk import setup_logging, get_logger, LogLevel, LogOutput

# 生产环境：INFO级别，仅输出到文件
setup_logging(
    level=LogLevel.INFO,
    output=LogOutput.FILE,
    log_file="/var/log/ha_sdk/app.log"
)

logger = get_logger(__name__)
logger.info("处理请求：%s", request_id)
logger.error("处理失败：%s", error_message)
```

### 示例 3：记录异常

```python
from home_assistant_sdk import get_logger

logger = get_logger(__name__)

try:
    # 可能抛出异常的代码
    result = risky_operation()
except Exception as e:
    # 记录异常信息（包含堆栈跟踪）
    logger.exception("操作失败")
    # 或者
    logger.error("操作失败: %s", str(e), exc_info=True)
```

## 高级配置

### 为不同模块使用不同配置

```python
from home_assistant_sdk import LoggerConfig, LoggerManager, LogLevel, LogOutput

# 为特定模块创建自定义配置
config = LoggerConfig(
    level=LogLevel.DEBUG,
    output=LogOutput.FILE,
    log_file="./logs/special.log"
)

# 获取使用自定义配置的logger
logger = LoggerManager.get_logger("special_module", config)
```

### 日志文件轮转配置

```python
from home_assistant_sdk import LoggerConfig, LogLevel, LogOutput

config = LoggerConfig(
    level=LogLevel.INFO,
    output=LogOutput.FILE,
    log_file="./logs/app.log",
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5                # 保留5个备份文件
)

# 当日志文件达到10MB时，会自动创建备份：
# app.log -> app.log.1 -> app.log.2 -> ... -> app.log.5
```

## 迁移说明

本项目已完成迁移，所有模块中的 `print` 语句（除 `if __name__ == "__main__"` 部分）都已替换为 `logger` 调用：

- `home_assistant_api.py` ✅
- `home_assistant_client.py` ✅（本身已使用logging）
- `xiaomi_home_flow.py` ✅
- `mcp_server_flow.py` ✅

### 迁移对照表

| 原代码 | 新代码 |
|--------|--------|
| `print(f"成功: {msg}")` | `logger.info(f"成功: {msg}")` |
| `print(f"警告: {msg}")` | `logger.warning(f"警告: {msg}")` |
| `print(f"错误: {msg}")` | `logger.error(f"错误: {msg}")` |
| `print(f"调试: {msg}")` | `logger.debug(f"调试: {msg}")` |

## 默认行为

如果不进行任何配置，模块将使用以下默认设置：
- **日志等级**: INFO
- **输出形式**: 仅控制台
- **日志格式**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **日期格式**: `%Y-%m-%d %H:%M:%S`

## 注意事项

1. **调用 `setup_logging()` 的时机**：应在程序启动时尽早调用，以确保所有模块使用统一配置
2. **文件路径**：使用 `LogOutput.FILE` 或 `LogOutput.BOTH` 时，确保日志目录存在或有权限创建
3. **性能考虑**：在生产环境中，建议将日志等级设置为 INFO 或更高，避免过多的 DEBUG 日志影响性能
4. **日志轮转**：默认启用日志文件轮转（单个文件最大10MB，保留5个备份），可根据需要调整

## 未来扩展

抽象的 `AbstractLogger` 类使得切换到其他日志框架变得简单。例如，如果将来想使用 `loguru`：

```python
# 只需修改 logger.py 中的 AbstractLogger 实现
# 业务代码无需修改
class AbstractLogger:
    def __init__(self, logger_name: str):
        from loguru import logger
        self._logger = logger.bind(name=logger_name)
    
    def info(self, msg: str, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)
    # ... 其他方法
```

## 相关资源

- [Python logging 官方文档](https://docs.python.org/3/library/logging.html)
- [Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [日志最佳实践](https://docs.python-guide.org/writing/logging/)
