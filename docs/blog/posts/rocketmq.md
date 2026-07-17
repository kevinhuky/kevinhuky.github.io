---
title: RocketMQ 技术笔记
description: 基于官方文档总结 RocketMQ 核心设计原理：消息存储模型、消费逻辑与 5.x 版本新特性。
draft: false
authors: [huyi]
date: 2025-06-27
slug: mq
categories:
  - Engineering
  - 终生学习
tags:
  - 消息队列
  - RocketMQ
---

本文基于 Apache RocketMQ 官方文档，总结核心设计原理与关键技术点，并记录学习过程中遇到的疑问与分析。内容涵盖消息存储模型、消费逻辑、5.x 版本特性等，适合作为个人技术笔记或开发者参考。<!-- more -->

# RocketMQ 技术笔记

## 一、RocketMQ 简介

Apache RocketMQ 是一款**分布式消息中间件**，最初由阿里巴巴开发，后捐赠给 Apache 基金会。它具有**高吞吐量、低延迟、高可用**等特点，广泛应用于电商、金融、物流等领域。

### 核心特性

- **高吞吐量**：单机支持百万级消息堆积
- **低延迟**：毫秒级消息投递
- **高可用**：支持主从复制和多副本机制
- **顺序消息**：支持全局顺序和分区顺序
- **事务消息**：支持分布式事务的最终一致性
- **消息回溯**：支持按时间回溯消费

---

## 二、核心架构

RocketMQ 的架构由四个核心组件组成：

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Producer   │───▶│   Broker    │◀───│  Consumer   │
└─────────────┘    └──────┬──────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  NameServer │
                   └─────────────┘
```

| 组件 | 职责 |
|------|------|
| **NameServer** | 轻量级注册中心，管理 Broker 的路由信息 |
| **Broker** | 消息存储和转发的核心，负责消息的持久化 |
| **Producer** | 消息生产者，负责发送消息 |
| **Consumer** | 消息消费者，负责消费消息 |

### NameServer vs ZooKeeper

RocketMQ 没有使用 ZooKeeper，而是自研了轻量级的 NameServer：

- **无状态**：各 NameServer 节点之间互不通信
- **简单高效**：仅存储路由信息，不做复杂协调
- **高可用**：通过部署多个节点实现

---

## 三、消息模型

### 3.1 Topic 与 Queue

```
Topic (逻辑概念)
    │
    ├── Queue 0  ──▶ Consumer A
    ├── Queue 1  ──▶ Consumer B  
    ├── Queue 2  ──▶ Consumer C
    └── Queue 3  ──▶ Consumer A (负载均衡)
```

- **Topic**：消息的逻辑分类，一个 Topic 可以分布在多个 Broker 上
- **Queue**：Topic 的物理分区，消息实际存储的单元
- **Tag**：消息的二级分类，用于过滤消息

### 3.2 消息存储模型

RocketMQ 采用 **CommitLog + ConsumeQueue** 的存储结构：

```
CommitLog (顺序写)
┌────────────────────────────────────────┐
│ Msg1 │ Msg2 │ Msg3 │ Msg4 │ Msg5 │ ... │
└────────────────────────────────────────┘
          │
          ▼ 异步构建
ConsumeQueue (索引)
┌─────────────────────────┐
│ offset │ size │ tagCode │  ──▶ 指向 CommitLog
└─────────────────────────┘
```

**设计优势**：

1. **顺序写**：所有消息追加写入 CommitLog，充分利用磁盘顺序写的高性能
2. **随机读**：通过 ConsumeQueue 索引快速定位消息
3. **零拷贝**：使用 mmap 内存映射，减少数据拷贝

---

## 四、消费者类型

RocketMQ 支持两种消费模式：

### 4.1 Push Consumer（推模式）

实际上是**长轮询**实现的"伪推送"，Broker 有消息时立即返回，无消息时挂起请求。

```java
// Push 模式示例
DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("ConsumerGroup");
consumer.subscribe("TopicTest", "*");
consumer.registerMessageListener((MessageListenerConcurrently) (msgs, context) -> {
    for (MessageExt msg : msgs) {
        System.out.println("收到消息: " + new String(msg.getBody()));
    }
    return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
});
consumer.start();
```

**特点**：
- 实时性高，消息到达后立即推送
- 适合大多数场景

### 4.2 Pull Consumer（拉模式）

消费者主动从 Broker 拉取消息，需要自己管理偏移量。

```java
// Pull 模式示例
DefaultLitePullConsumer consumer = new DefaultLitePullConsumer("ConsumerGroup");
consumer.subscribe("TopicTest", "*");
consumer.start();

while (true) {
    List<MessageExt> msgs = consumer.poll();
    for (MessageExt msg : msgs) {
        System.out.println("拉取消息: " + new String(msg.getBody()));
    }
}
```

**特点**：
- 消费节奏由消费者控制
- 适合批量处理、流量控制场景

---

## 五、顺序消息

### 5.1 全局顺序

所有消息发送到**同一个 Queue**，保证全局有序。

```java
// 全局顺序：Topic 只配置一个 Queue
producer.send(msg, (mqs, msg1, arg) -> mqs.get(0), orderId);
```

**缺点**：吞吐量受限于单个 Queue

### 5.2 分区顺序（推荐）

同一业务 ID 的消息发送到**同一个 Queue**，保证局部有序。

```java
// 分区顺序：按订单ID路由到同一Queue
producer.send(msg, (mqs, msg1, arg) -> {
    Long orderId = (Long) arg;
    int index = (int) (orderId % mqs.size());
    return mqs.get(index);
}, orderId);
```

**适用场景**：订单状态流转（创建→支付→发货→完成）

---

## 六、事务消息

RocketMQ 事务消息采用**二阶段提交 + 事务回查**机制：

```
┌──────────┐     1. 发送半消息      ┌──────────┐
│ Producer │ ──────────────────────▶│  Broker  │
└──────────┘                        └──────────┘
     │                                    │
     │ 2. 执行本地事务                      │
     ▼                                    │
┌──────────┐     3. 提交/回滚        ┌──────────┐
│  本地DB  │ ◀─────────────────────│  Broker  │
└──────────┘                        └──────────┘
                                          │
                    4. 事务回查（超时未确认） │
                 ◀────────────────────────┘
```

### 实现步骤

```java
TransactionMQProducer producer = new TransactionMQProducer("TransGroup");
producer.setTransactionListener(new TransactionListener() {
    @Override
    public LocalTransactionState executeLocalTransaction(Message msg, Object arg) {
        // 执行本地事务
        try {
            orderService.createOrder(msg);
            return LocalTransactionState.COMMIT_MESSAGE;
        } catch (Exception e) {
            return LocalTransactionState.ROLLBACK_MESSAGE;
        }
    }
    
    @Override
    public LocalTransactionState checkLocalTransaction(MessageExt msg) {
        // 事务回查：检查本地事务状态
        String orderId = msg.getKeys();
        if (orderService.exists(orderId)) {
            return LocalTransactionState.COMMIT_MESSAGE;
        }
        return LocalTransactionState.ROLLBACK_MESSAGE;
    }
});
```

---

## 七、消息重试与死信队列

### 7.1 消费重试

消费失败时，RocketMQ 会自动进行重试：

| 重试次数 | 间隔时间 |
|---------|---------|
| 1 | 10s |
| 2 | 30s |
| 3 | 1min |
| 4 | 2min |
| ... | 递增 |
| 16 | 2h |

### 7.2 死信队列（DLQ）

超过最大重试次数后，消息进入死信队列：`%DLQ%ConsumerGroup`

```java
// 消费死信队列
consumer.subscribe("%DLQ%ConsumerGroup", "*");
```

**处理策略**：
- 人工介入处理
- 定时任务重新投递
- 告警通知

---

## 八、高可用部署

### 8.1 集群模式

| 模式 | 描述 | 特点 |
|------|------|------|
| **单 Master** | 单节点部署 | 简单，无高可用 |
| **多 Master** | 多个 Master 节点 | 高可用，但 Master 宕机会丢失未同步消息 |
| **多 Master 多 Slave（异步）** | 主从异步复制 | 高吞吐，可能丢少量消息 |
| **多 Master 多 Slave（同步）** | 主从同步复制 | 数据零丢失，延迟略高 |

### 8.2 Dledger 模式（推荐）

RocketMQ 4.5+ 引入基于 Raft 协议的 Dledger 模式：

- **自动选主**：Master 宕机后自动选举新 Master
- **数据强一致**：基于 Raft 协议保证数据一致性
- **无需人工干预**：真正的高可用

---

## 九、性能优化建议

### 生产者优化

1. **批量发送**：合并多条消息一次发送
2. **异步发送**：非关键消息使用异步模式
3. **消息压缩**：大消息启用压缩

### 消费者优化

1. **增加消费线程**：`consumeThreadMin/consumeThreadMax`
2. **批量消费**：`consumeMessageBatchMaxSize`
3. **跳过非重要消息**：设置消费超时时间

### Broker 优化

1. **SSD 存储**：提升 IO 性能
2. **调整内存**：合理配置 JVM 和 PageCache
3. **异步刷盘**：非金融场景可使用 `ASYNC_FLUSH`

---

## 十、常见问题 FAQ

### Q1: 消息堆积怎么处理？

1. 增加消费者实例数量
2. 提高单个消费者的并发线程数
3. 临时扩容 Queue 数量

### Q2: 如何保证消息不丢失？

| 阶段 | 保证措施 |
|------|---------|
| 生产端 | 同步发送 + 重试机制 |
| Broker | 同步刷盘 + 主从同步复制 |
| 消费端 | 手动提交 offset + 幂等处理 |

### Q3: 如何实现消息幂等？

- **数据库唯一索引**：利用业务主键去重
- **Redis 记录**：记录已消费的 msgId
- **状态机**：检查业务状态是否允许执行

---

> **参考资料**：
> - [Apache RocketMQ 官方文档](https://rocketmq.apache.org/docs/)
> - 《RocketMQ 技术内幕》
