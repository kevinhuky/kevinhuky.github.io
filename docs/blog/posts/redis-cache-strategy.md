---
title: Redis 缓存策略与常见问题解决方案
description: 深入讲解 Redis 缓存策略、数据结构选型，以及缓存穿透、击穿、雪崩等常见问题的解决方案。
draft: false
authors: [huyi]
date: 2025-09-01
slug: redis-cache-strategy
categories:
  - Engineering
  - 终生学习
tags:
  - Redis
  - 缓存
---

Redis 是最流行的内存数据库之一，广泛用于缓存、会话管理、排行榜等场景。本文深入讲解 Redis 缓存策略、数据结构选型、以及缓存穿透、击穿、雪崩等常见问题的解决方案。<!-- more -->

# Redis 缓存策略与常见问题解决方案

## 一、Redis 简介

### 1.1 什么是 Redis？

Redis（Remote Dictionary Server）是一个开源的**内存数据结构存储系统**，可以用作数据库、缓存和消息中间件。

**核心特点**：

- **高性能**：基于内存，读写速度极快（10万+ QPS）
- **丰富的数据结构**：String、Hash、List、Set、ZSet 等
- **持久化**：支持 RDB 和 AOF 两种持久化方式
- **高可用**：支持主从复制、哨兵、集群模式
- **原子操作**：所有操作都是原子的

### 1.2 Redis vs Memcached

| 特性 | Redis | Memcached |
|------|-------|-----------|
| 数据结构 | 丰富（5种+） | 仅 String |
| 持久化 | 支持 | 不支持 |
| 集群 | 原生支持 | 需客户端实现 |
| 线程模型 | 单线程（6.0 多线程IO） | 多线程 |
| 内存管理 | 自主实现 | Slab Allocation |

---

## 二、Redis 数据结构与应用场景

### 2.1 String（字符串）

最基本的数据类型，可以存储字符串、整数或浮点数。

```bash
# 基本操作
SET user:1:name "张三"
GET user:1:name

# 计数器
INCR article:1:views      # 文章阅读量
INCRBY user:1:points 10   # 用户积分增加

# 分布式锁
SET lock:order:123 "uuid" NX EX 30  # 30秒过期的锁

# 缓存对象（JSON）
SET user:1 '{"id":1,"name":"张三","age":25}'
```

**应用场景**：缓存、计数器、分布式锁、Session 存储

### 2.2 Hash（哈希）

键值对集合，适合存储对象。

```bash
# 存储用户信息
HSET user:1 name "张三" age 25 email "zhangsan@example.com"
HGET user:1 name
HGETALL user:1

# 购物车
HSET cart:user:1 product:1001 2  # 商品1001，数量2
HINCRBY cart:user:1 product:1001 1  # 数量+1
HDEL cart:user:1 product:1001  # 删除商品
```

**应用场景**：对象存储、购物车、用户属性

### 2.3 List（列表）

双向链表，支持从两端操作。

```bash
# 消息队列
LPUSH queue:email "message1"  # 生产者
RPOP queue:email              # 消费者
BRPOP queue:email 30          # 阻塞式消费，30秒超时

# 最新列表
LPUSH news:latest "article:1001"
LTRIM news:latest 0 99  # 只保留最新100条
LRANGE news:latest 0 9  # 获取最新10条
```

**应用场景**：消息队列、最新列表、时间线

### 2.4 Set（集合）

无序且唯一的字符串集合。

```bash
# 标签系统
SADD article:1:tags "Java" "Redis" "后端"
SMEMBERS article:1:tags  # 获取所有标签

# 共同关注
SADD user:1:follows 2 3 4 5
SADD user:2:follows 3 4 6 7
SINTER user:1:follows user:2:follows  # 共同关注：3, 4

# 抽奖
SADD lottery:1 user:1 user:2 user:3
SRANDMEMBER lottery:1 2  # 随机抽取2人
SPOP lottery:1           # 抽取并移除（不可重复中奖）
```

**应用场景**：标签、共同好友、去重、抽奖

### 2.5 ZSet（有序集合）

带分数的有序集合，按分数排序。

```bash
# 排行榜
ZADD leaderboard 1000 "user:1" 800 "user:2" 1200 "user:3"
ZREVRANGE leaderboard 0 9 WITHSCORES  # Top 10
ZRANK leaderboard "user:1"            # 获取排名
ZINCRBY leaderboard 50 "user:1"       # 增加分数

# 延迟队列
ZADD delay:queue 1705123456 "task:1"  # 分数为执行时间戳
ZRANGEBYSCORE delay:queue 0 1705123456  # 获取到期任务
```

**应用场景**：排行榜、延迟队列、范围查询

---

## 三、缓存策略

### 3.1 Cache Aside（旁路缓存）

最常用的缓存策略，应用程序同时维护缓存和数据库。

```
读取流程：
1. 先读缓存
2. 缓存命中 → 返回数据
3. 缓存未命中 → 读数据库 → 写入缓存 → 返回数据

写入流程：
1. 更新数据库
2. 删除缓存（不是更新缓存！）
```

```java
// 读取
public User getUser(Long userId) {
    String key = "user:" + userId;
    
    // 1. 查缓存
    String cached = redis.get(key);
    if (cached != null) {
        return JSON.parseObject(cached, User.class);
    }
    
    // 2. 查数据库
    User user = userMapper.selectById(userId);
    if (user != null) {
        // 3. 写缓存
        redis.setex(key, 3600, JSON.toJSONString(user));
    }
    return user;
}

// 写入
@Transactional
public void updateUser(User user) {
    // 1. 更新数据库
    userMapper.updateById(user);
    // 2. 删除缓存
    redis.del("user:" + user.getId());
}
```

**为什么删除缓存而不是更新缓存？**

1. 避免并发下的数据不一致
2. 懒加载思想，下次读取时再更新

### 3.2 Read/Write Through

应用程序只与缓存交互，缓存负责与数据库同步。

```
读取：缓存未命中时，缓存自动加载数据库数据
写入：写缓存，缓存同步写入数据库
```

适合缓存中间件支持此模式的场景。

### 3.3 Write Behind（异步写回）

写入时只更新缓存，异步批量写入数据库。

```
优点：写入性能极高
缺点：可能丢数据（缓存宕机时）
```

适合写入频繁、允许少量数据丢失的场景（如计数器）。

---

## 四、缓存常见问题

### 4.1 缓存穿透

**定义**：查询不存在的数据，缓存未命中，每次都查数据库。

```
攻击者：大量请求不存在的 ID（如负数、超大数）
结果：数据库压力骤增
```

**解决方案**：

#### 方案一：缓存空值

```java
public User getUser(Long userId) {
    String key = "user:" + userId;
    String cached = redis.get(key);
    
    // 空值也认为是命中
    if (cached != null) {
        return "NULL".equals(cached) ? null : JSON.parseObject(cached, User.class);
    }
    
    User user = userMapper.selectById(userId);
    if (user != null) {
        redis.setex(key, 3600, JSON.toJSONString(user));
    } else {
        // 缓存空值，设置较短过期时间
        redis.setex(key, 300, "NULL");
    }
    return user;
}
```

#### 方案二：布隆过滤器

```java
// 初始化时加载所有存在的 ID 到布隆过滤器
BloomFilter<Long> bloomFilter = BloomFilter.create(
    Funnels.longFunnel(), 1000000, 0.01  // 百万数据，1%误判率
);

// 加载数据
List<Long> allUserIds = userMapper.selectAllIds();
allUserIds.forEach(bloomFilter::put);

// 查询时先判断
public User getUser(Long userId) {
    // 布隆过滤器判断，不存在则一定不存在
    if (!bloomFilter.mightContain(userId)) {
        return null;
    }
    // 正常查询逻辑...
}
```

### 4.2 缓存击穿

**定义**：热点 Key 过期瞬间，大量请求同时查数据库。

```
场景：某热门商品缓存过期
结果：瞬间大量请求打到数据库
```

**解决方案**：

#### 方案一：互斥锁

```java
public User getUser(Long userId) {
    String key = "user:" + userId;
    String cached = redis.get(key);
    
    if (cached != null) {
        return JSON.parseObject(cached, User.class);
    }
    
    // 获取分布式锁
    String lockKey = "lock:user:" + userId;
    boolean locked = redis.setnx(lockKey, "1", 10);
    
    try {
        if (locked) {
            // 获取锁成功，查询数据库
            User user = userMapper.selectById(userId);
            redis.setex(key, 3600, JSON.toJSONString(user));
            return user;
        } else {
            // 获取锁失败，等待后重试
            Thread.sleep(100);
            return getUser(userId);
        }
    } finally {
        if (locked) {
            redis.del(lockKey);
        }
    }
}
```

#### 方案二：逻辑过期

```java
@Data
public class CacheData {
    private Object data;
    private long expireTime;  // 逻辑过期时间
}

public User getUser(Long userId) {
    String key = "user:" + userId;
    CacheData cacheData = redis.get(key);
    
    if (cacheData == null) {
        return null;  // 缓存预热时加载
    }
    
    // 未过期，直接返回
    if (System.currentTimeMillis() < cacheData.getExpireTime()) {
        return (User) cacheData.getData();
    }
    
    // 已过期，异步更新缓存
    if (tryLock(key)) {
        executor.submit(() -> {
            try {
                User user = userMapper.selectById(userId);
                CacheData newData = new CacheData(user, System.currentTimeMillis() + 3600000);
                redis.set(key, newData);
            } finally {
                unlock(key);
            }
        });
    }
    
    // 返回旧数据
    return (User) cacheData.getData();
}
```

### 4.3 缓存雪崩

**定义**：大量缓存同时过期，或 Redis 宕机，导致数据库压力骤增。

```
场景1：批量导入数据，设置相同过期时间
场景2：Redis 集群故障
```

**解决方案**：

#### 方案一：过期时间加随机值

```java
// 避免同时过期
int baseExpire = 3600;
int randomExpire = new Random().nextInt(600);  // 0-600秒随机
redis.setex(key, baseExpire + randomExpire, value);
```

#### 方案二：多级缓存

```
请求 → 本地缓存(Caffeine) → Redis → 数据库
```

```java
@Service
public class UserService {
    
    // 本地缓存
    private final Cache<Long, User> localCache = Caffeine.newBuilder()
            .maximumSize(10000)
            .expireAfterWrite(5, TimeUnit.MINUTES)
            .build();
    
    public User getUser(Long userId) {
        // 1. 本地缓存
        User user = localCache.getIfPresent(userId);
        if (user != null) {
            return user;
        }
        
        // 2. Redis 缓存
        String key = "user:" + userId;
        String cached = redis.get(key);
        if (cached != null) {
            user = JSON.parseObject(cached, User.class);
            localCache.put(userId, user);
            return user;
        }
        
        // 3. 数据库
        user = userMapper.selectById(userId);
        if (user != null) {
            redis.setex(key, 3600, JSON.toJSONString(user));
            localCache.put(userId, user);
        }
        return user;
    }
}
```

#### 方案三：熔断降级

```java
// 使用 Sentinel 或 Hystrix
@SentinelResource(value = "getUser", fallback = "getUserFallback")
public User getUser(Long userId) {
    // 正常逻辑
}

public User getUserFallback(Long userId) {
    // 降级逻辑：返回默认值或友好提示
    return new User().setName("系统繁忙");
}
```

---

## 五、缓存一致性

### 5.1 延迟双删

确保缓存与数据库最终一致。

```java
@Transactional
public void updateUser(User user) {
    String key = "user:" + user.getId();
    
    // 1. 先删缓存
    redis.del(key);
    
    // 2. 更新数据库
    userMapper.updateById(user);
    
    // 3. 延迟再删一次（处理并发读导致的脏数据）
    executor.schedule(() -> redis.del(key), 500, TimeUnit.MILLISECONDS);
}
```

### 5.2 Canal 订阅 Binlog

通过监听 MySQL Binlog 实现缓存更新。

```
MySQL → Binlog → Canal → MQ → 缓存更新服务 → Redis
```

**优点**：
- 解耦应用程序与缓存更新逻辑
- 保证最终一致性
- 支持增量同步

---

## 六、Redis 高可用

### 6.1 主从复制

```
Master(写) → Slave1(读)
          → Slave2(读)
```

```bash
# 从节点配置
replicaof 192.168.1.100 6379
```

### 6.2 哨兵模式（Sentinel）

自动故障转移。

```
     ┌──────────┐
     │ Sentinel │ ← 监控
     └──────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌────────┐   ┌────────┐
│ Master │   │ Slave  │
└────────┘   └────────┘
    故障 ↓        ↑ 升级
         └────────┘
```

### 6.3 集群模式（Cluster）

数据分片，水平扩展。

```
┌─────────────────────────────────────┐
│           16384 个槽位               │
├───────────┬───────────┬─────────────┤
│ 0-5460    │ 5461-10922│ 10923-16383 │
│  Node 1   │  Node 2   │   Node 3    │
│ (Master)  │ (Master)  │  (Master)   │
│    ↓      │    ↓      │     ↓       │
│  Slave    │  Slave    │   Slave     │
└───────────┴───────────┴─────────────┘
```

---

## 七、Redis 性能优化

### 7.1 键设计规范

```bash
# ✅ 好的键名
user:1001:profile
order:2024:01:20:123456
cache:product:category:electronics

# ❌ 差的键名
u1001        # 太短，含义不明
user_profile_for_user_id_1001  # 太长
user:*:data  # 避免使用通配符
```

### 7.2 避免大 Key

```bash
# 检测大 Key
redis-cli --bigkeys

# 大 Key 的危害
# - 网络传输慢
# - 阻塞其他请求
# - 主从同步延迟

# 解决方案：拆分
# Hash 拆分
HSET user:1:basic name "张三" age 25
HSET user:1:detail address "xxx" bio "xxx"

# List 拆分
LPUSH user:1:orders:2024 ...
LPUSH user:1:orders:2023 ...
```

### 7.3 管道（Pipeline）

批量操作减少网络往返。

```java
// ❌ 多次网络请求
for (int i = 0; i < 1000; i++) {
    redis.set("key:" + i, "value");
}

// ✅ 使用 Pipeline
Pipeline pipeline = redis.pipelined();
for (int i = 0; i < 1000; i++) {
    pipeline.set("key:" + i, "value");
}
pipeline.sync();  // 一次网络请求
```

### 7.4 Lua 脚本

保证原子性操作。

```lua
-- 限流脚本
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('GET', key)
if current and tonumber(current) >= limit then
    return 0  -- 超过限制
end

current = redis.call('INCR', key)
if tonumber(current) == 1 then
    redis.call('EXPIRE', key, window)
end
return 1  -- 允许通过
```

```java
// Java 调用
String script = "...";
Long result = redis.eval(script, 
    Collections.singletonList("rate:user:1"), 
    Arrays.asList("10", "60"));  // 60秒内限制10次
```

---

## 八、实战案例

### 8.1 分布式锁

```java
public class RedisLock {
    private static final String LOCK_SUCCESS = "OK";
    private static final String RELEASE_SCRIPT = 
        "if redis.call('get', KEYS[1]) == ARGV[1] then " +
        "   return redis.call('del', KEYS[1]) " +
        "else " +
        "   return 0 " +
        "end";
    
    public boolean tryLock(String lockKey, String requestId, int expireTime) {
        String result = redis.set(lockKey, requestId, "NX", "EX", expireTime);
        return LOCK_SUCCESS.equals(result);
    }
    
    public boolean releaseLock(String lockKey, String requestId) {
        Long result = redis.eval(RELEASE_SCRIPT, 
            Collections.singletonList(lockKey),
            Collections.singletonList(requestId));
        return result == 1L;
    }
}
```

### 8.2 限流器

```java
// 滑动窗口限流
public boolean isAllowed(String userId, int maxRequests, int windowSeconds) {
    String key = "rate:" + userId;
    long now = System.currentTimeMillis();
    long windowStart = now - windowSeconds * 1000;
    
    // 使用 ZSet 实现滑动窗口
    Pipeline pipeline = redis.pipelined();
    pipeline.zremrangeByScore(key, 0, windowStart);  // 移除窗口外的请求
    pipeline.zadd(key, now, String.valueOf(now));    // 添加当前请求
    pipeline.zcard(key);                              // 统计窗口内请求数
    pipeline.expire(key, windowSeconds);              // 设置过期时间
    List<Object> results = pipeline.syncAndReturnAll();
    
    Long count = (Long) results.get(2);
    return count <= maxRequests;
}
```

### 8.3 排行榜

```java
// 更新分数
public void updateScore(String leaderboardKey, String userId, double score) {
    redis.zincrby(leaderboardKey, score, userId);
}

// 获取 Top N
public List<RankItem> getTopN(String leaderboardKey, int n) {
    Set<Tuple> tuples = redis.zrevrangeWithScores(leaderboardKey, 0, n - 1);
    return tuples.stream()
        .map(t -> new RankItem(t.getElement(), t.getScore()))
        .collect(Collectors.toList());
}

// 获取用户排名
public Long getUserRank(String leaderboardKey, String userId) {
    return redis.zrevrank(leaderboardKey, userId);
}
```

---

## 九、总结

### 缓存策略选择

| 场景 | 推荐策略 |
|------|---------|
| 读多写少 | Cache Aside |
| 写多读少 | Write Behind |
| 一致性要求高 | Read/Write Through |

### 问题解决速查

| 问题 | 解决方案 |
|------|---------|
| 缓存穿透 | 空值缓存 / 布隆过滤器 |
| 缓存击穿 | 互斥锁 / 逻辑过期 |
| 缓存雪崩 | 随机过期 / 多级缓存 / 熔断降级 |
| 数据一致性 | 延迟双删 / Canal 订阅 |

### 核心要点

1. **选择合适的数据结构**：不同场景使用不同类型
2. **设计合理的缓存策略**：根据业务特点选择
3. **处理好缓存问题**：穿透、击穿、雪崩
4. **保证高可用**：主从、哨兵、集群
5. **持续优化性能**：Pipeline、Lua、避免大 Key

---

> **参考资料**：
> - [Redis 官方文档](https://redis.io/documentation)
> - 《Redis 设计与实现》
> - 《Redis 深度历险》
