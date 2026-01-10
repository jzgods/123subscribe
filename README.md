# 📁 123云盘分享监控程序

一个用于监控123云盘分享链接内容变更，并自动将更新的文件转存到自己云盘的后台程序。

## ✨ 功能特性

- 📊 **多链接监控**：监控多个123云盘分享链接的内容变更
- 📥 **自动同步**：自动将新增或更新的文件转存到指定的目标文件夹（根据MD5校验和判断是否更新或新增）
- ⏰ **定时任务**：支持定时自动执行监控任务
- 🚀 **多线程处理**：支持多线程并发处理多个分享链接

## ⚠️ 注意事项

- ⚠️ **全量同步**：由于暂时没有开发指定文件后才更新的功能，所以每次新增分享链接后会全量同步到指定文件夹内！
- ⚠️ **配置文件**：请不要随意修改conf内的配置文件，否则可能导致程序异常运行，导致云盘文件混乱！

## 🚀 快速开始

### 📦 安装与部署

本项目已提供Docker镜像，您可以直接使用本地的Docker Compose文件进行部署。

#### 🐳 镜像拉取

```bash
docker pull zhuangjay/123subscrib:latest
```

#### 🛠️ 使用Docker Compose部署（推荐）

1. ✅ 确保您已安装Docker和Docker Compose

2. 📄 直接使用该项目的`docker-compose.yml`文件

### 🌐 访问服务

容器运行后，可以通过以下地址访问服务：
- 🖥️ Web界面：http://IP:24512

## ⚙️ 详细配置说明

### 📄 配置文件结构

配置文件位于`conf/config.yaml`，包含以下主要部分（所有配置均可在前端界面设置）：

```yaml
api:
  client_id: "your_client_id"
  client_secret: "your_client_secret"
  retry_attempts: 3
  retry_delay: 2.0
  timeout: 30.0
sync:
  max_retries: 3
  thread_pool_size: 0  # 线程池大小，0表示不启用多线程，-1表示不限制，>0表示具体线程数
monitored_shares:
  - url: ""
    enabled: true
    target_folder_id: "your_target_folder_id"
    preserve_path: true
    duplicate: 2  # 文件重名处理方式：1保留两个文件，2直接覆盖
  - url: ""
    enabled: false
    target_folder_id: "your_another_folder_id"
    password: "your_password"  # 单独指定提取码
logging:
  level: "INFO"
  log_file: "./logs/123subscrib.log"
  max_bytes: 10485760
  backup_count: 5
scheduler:
  interval_minutes: 60  # 全局监控间隔（分钟）
  max_history: 1000
```

### 🔧 配置项说明

#### 🔌 API配置 (api)

- 📝 **申请开发者**：开放平台API调用需在123云盘开放平台申请成为开发者，申请后一般2-3个工作日ID和SECRET会通过邮件发送到您的注册邮箱
- `client_id`: 开放平台ID
- `client_secret`: 开放平台密钥
- `retry_attempts`: 请求重试次数
- `retry_delay`: 重试间隔(秒)
- `timeout`: 请求超时时间(秒)

#### 🔄 同步配置 (sync)

- `max_retries`: 最大重试次数
- `thread_pool_size`: 线程池大小
  - 0: 不启用多线程
  - -1: 不限制线程数
  - >0: 具体线程数量

#### 📋 监控配置 (monitored_shares)

这是一个数组，可以配置多个分享链接：

- `url`: 123云盘分享链接
- `enabled`: 是否启用监控
- `target_folder_id`: 目标文件夹ID，云盘内右键点击文件夹，选择“复制文件夹ID”粘贴过来即可，若为根目录则为0
- `preserve_path`: 是否保留原文件路径结构，默认值为false，若为true则会在目标文件夹下创建与原路径相同的子文件夹
- `duplicate`: 文件重名处理方式
  - 1: 保留两个文件
  - 2: 直接覆盖（默认）
- `password`: 分享链接提取码（可选，可从URL自动提取）

#### ⏰ 调度器配置 (scheduler)

- `interval_minutes`: 监控间隔(分钟)
- `max_history`: 保留的最大历史记录数

#### 📊 日志配置 (logging)

- `level`: 日志级别，可选值：DEBUG, INFO, WARNING, ERROR
- `log_file`: 日志文件路径
- `max_bytes`: 单个日志文件最大大小(字节)
- `backup_count`: 保留的日志文件数量

## 📍 环境变量

| 环境变量 | 描述 | 默认值 |
|---------|------|--------|
| APP_USERNAME | 访问服务的用户名 | 空字符串 |
| APP_PASSWORD | 访问服务的密码 | 空字符串 |

## 📌 注意事项

1. 📁 目标文件夹ID(`target_folder_id`)必须是您账户中已存在的文件夹
2. ⏱️ 频繁的API调用可能会触发速率限制，可通过调整监控间隔来避免，建议设置为60分钟以上
3. 🚀 线程池大小建议根据系统资源和监控链接数量合理设置

## 📄 免责声明

使用本程序时请遵守123云盘的用户协议和相关规定。本程序仅用于学习和个人使用，请勿用于任何违反法律法规的用途。
