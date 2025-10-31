# 日志系统迁移总结

## 概述

本次更新将项目中所有 Python 文件的 `print` 语句（除了 `if __name__ == "__main__"` 部分）替换为统一的日志管理系统。

## 新增文件

### 1. `src/home_assistant_sdk/logger.py`
全局日志管理模块，提供以下核心功能：

#### 主要类

- **`LogLevel`**: 日志等级枚举（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- **`LogOutput`**: 输出形式枚举（CONSOLE, FILE, BOTH）
- **`LoggerConfig`**: 日志配置类
  - 支持日志等级配置
  - 支持输出形式配置（控制台、文件、或两者）
  - 支持自定义日志格式
  - 支持日志文件轮转（默认10MB，保留5个备份）
  
- **`LoggerManager`**: 日志管理器
  - 全局默认配置管理
  - Logger 实例缓存
  - 根 logger 配置

- **`AbstractLogger`**: 抽象日志接口
  - 封装标准库 logging API
  - 方便未来切换到其他日志框架（如 loguru, structlog）
  - 提供 debug, info, warning, error, critical, exception 方法

#### 便捷函数

- **`get_logger(name, level=None, output=None, log_file=None)`**: 
  获取 logger 实例的便捷函数

- **`setup_logging(level, output, log_file, format_string, date_format)`**: 
  设置全局日志配置的便捷函数

### 2. `LOGGING_GUIDE.md`
详细的日志模块使用指南，包含：
- 快速开始示例
- 日志等级说明
- 输出形式说明
- 完整使用示例
- 高级配置说明
- 迁移对照表

### 3. `test_logging.py`
日志模块测试脚本，验证以下功能：
- ✅ 控制台输出
- ✅ 文件输出
- ✅ 同时输出到控制台和文件
- ✅ 自定义格式
- ✅ 异常记录（包含堆栈跟踪）
- ✅ 不同日志等级过滤
- ✅ 模块集成

## 修改的文件

### 1. `src/home_assistant_sdk/home_assistant_api.py`
**修改内容**：
- 导入日志模块：`from .logger import get_logger`
- 创建模块 logger：`logger = get_logger(__name__)`
- 替换所有 print 语句为对应的 logger 调用

**修改位置**：
- `get_token()` 方法中的策略日志
- `_is_access_token_valid()` 方法中的验证日志
- `_load_token_from_cache()` 方法中的错误日志
- `_save_token()` 方法中的保存日志
- `_login_with_credentials()` 方法中的步骤日志

**日志等级映射**：
- 成功信息 → `logger.info()`
- 警告信息 → `logger.warning()`
- 调试信息 → `logger.debug()`

### 2. `src/home_assistant_sdk/xiaomi_home_flow.py`
**修改内容**：
- 导入日志模块：`from .logger import get_logger`
- 创建模块 logger：`logger = get_logger(__name__)`
- 替换 `run_full_flow()` 方法中的所有 print 语句

**修改位置**：
- 流程步骤信息（Step 1-6）
- 成功/失败状态信息
- OAuth URL 显示（保留在 `if __name__ == "__main__"` 中使用 print）

### 3. `src/home_assistant_sdk/mcp_server_flow.py`
**修改内容**：
- 导入日志模块：`from .logger import get_logger`
- 创建模块 logger：`logger = get_logger(__name__)`
- 替换 `setup_integration()` 和 `setup_mcp_server_integration()` 中的 print 语句

**修改位置**：
- 流程步骤信息
- 成功状态信息
- Entry ID 显示

### 4. `src/home_assistant_sdk/__init__.py`
**修改内容**：
- 导出日志管理模块的公共接口：
  ```python
  from .logger import (
      get_logger,
      setup_logging,
      LogLevel,
      LogOutput,
      LoggerConfig,
      LoggerManager,
      AbstractLogger,
  )
  ```
- 更新 `__all__` 列表，添加日志相关导出

### 5. `src/home_assistant_sdk/home_assistant_client.py`
**无需修改**：该文件本身已经使用了标准库的 logging 模块，符合要求。

## 保留的 print 语句

根据要求，以下位置的 print 语句被保留（都在 `if __name__ == "__main__"` 块中）：

1. **`home_assistant_api.py`** - 示例代码中的 print
2. **`xiaomi_home_flow.py`** - OAuth URL 显示、成功/失败提示
3. **`mcp_server_flow.py`** - 环境变量提示
4. **`__init__.py`** - main() 函数中的模块信息显示

## 设计特点

### 1. 结构清晰
- 单一职责：每个类负责明确的功能
- 分层设计：配置层、管理层、抽象层
- 模块化：易于扩展和维护

### 2. 灵活配置
- 支持全局配置和模块级配置
- 支持运行时动态调整
- 支持多种输出形式组合

### 3. 易于使用
- 提供便捷函数简化使用
- 默认配置开箱即用
- API 设计直观

### 4. 面向未来
- 抽象接口设计，方便切换日志框架
- 保持与标准库 logging 兼容
- 预留扩展点

### 5. 注释清晰
- 每个类、方法都有详细的文档字符串
- 参数说明完整
- 包含使用示例

## 使用示例

### 基础使用（使用默认配置）

```python
from home_assistant_sdk import get_logger

logger = get_logger(__name__)
logger.info("这是一条信息日志")
logger.error("这是一条错误日志")
```

### 配置日志输出

```python
from home_assistant_sdk import setup_logging, LogLevel, LogOutput

# 仅控制台
setup_logging(level=LogLevel.INFO, output=LogOutput.CONSOLE)

# 仅文件
setup_logging(
    level=LogLevel.DEBUG,
    output=LogOutput.FILE,
    log_file="./logs/app.log"
)

# 同时输出
setup_logging(
    level=LogLevel.INFO,
    output=LogOutput.BOTH,
    log_file="./logs/app.log"
)
```

### 在应用中使用

```python
# 在应用启动时配置
from home_assistant_sdk import setup_logging, get_logger, LogLevel, LogOutput

# 配置全局日志
setup_logging(
    level=LogLevel.INFO,
    output=LogOutput.BOTH,
    log_file="./logs/ha_sdk.log"
)

# 在各个模块中使用
logger = get_logger(__name__)
logger.info("应用启动")

try:
    # 业务逻辑
    result = do_something()
    logger.info(f"操作成功: {result}")
except Exception as e:
    logger.exception("操作失败")
```

## 测试验证

运行测试脚本验证功能：

```bash
python test_logging.py
```

测试涵盖：
- ✅ 控制台输出测试
- ✅ 文件输出测试
- ✅ 双重输出测试
- ✅ 自定义格式测试
- ✅ 异常记录测试
- ✅ 不同日志等级测试
- ✅ 模块集成测试

## 后续建议

1. **开发环境配置**：
   ```python
   setup_logging(
       level=LogLevel.DEBUG,
       output=LogOutput.BOTH,
       log_file="./logs/dev.log"
   )
   ```

2. **生产环境配置**：
   ```python
   setup_logging(
       level=LogLevel.INFO,
       output=LogOutput.FILE,
       log_file="/var/log/ha_sdk/app.log"
   )
   ```

3. **日志文件管理**：
   - 定期检查日志文件大小
   - 考虑使用日志收集系统（如 ELK、Loki 等）
   - 设置合适的日志轮转参数

4. **性能优化**：
   - 生产环境避免使用 DEBUG 级别
   - 考虑异步日志写入（如使用 QueueHandler）
   - 合理设置日志格式复杂度

## 兼容性

- Python 3.10+
- 基于标准库 logging，无额外依赖
- 向后兼容：不影响现有代码的 `if __name__ == "__main__"` 部分

## 总结

本次迁移成功地将项目的日志系统统一化、规范化，具有以下优势：

✅ **统一管理**：所有模块使用统一的日志配置  
✅ **灵活配置**：支持多种输出形式和等级  
✅ **易于维护**：清晰的代码结构和完善的注释  
✅ **面向未来**：抽象设计方便后续扩展  
✅ **生产就绪**：支持日志轮转和异常追踪  

详细使用方法请参考 [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md)。
