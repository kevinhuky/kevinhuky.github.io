---
title: MySQL 索引优化实战指南
description: 从索引原理出发，讲解 MySQL 索引类型、创建原则、优化技巧与常见索引失效场景，帮你写出更高效的 SQL。
draft: false
authors: [huyi]
date: 2025-08-10
slug: mysql-index-optimization
categories:
  - Engineering
  - 终生学习
tags:
  - MySQL
  - 数据库
---

索引是数据库性能优化的重要手段，本文从索引原理出发，详细讲解索引的类型、创建原则、优化技巧以及常见的索引失效场景，帮助你写出更高效的 SQL。<!-- more -->

# MySQL 索引优化实战指南

## 一、索引基础

### 1.1 什么是索引？

索引是一种**数据结构**，用于帮助数据库快速定位数据。类似于书的目录，通过目录可以快速找到特定章节，而不需要翻阅整本书。

**没有索引的查询**：全表扫描，逐行比对
**有索引的查询**：通过索引结构快速定位

### 1.2 索引的优缺点

| 优点 | 缺点 |
|------|------|
| 大幅提高查询速度 | 占用额外存储空间 |
| 加速排序和分组 | 降低写操作性能（INSERT/UPDATE/DELETE） |
| 保证数据唯一性（唯一索引） | 需要维护成本 |

---

## 二、索引数据结构

### 2.1 B+ 树（MySQL InnoDB 默认）

```
                    [15, 30]
                   /    |    \
            [5, 10]  [20, 25]  [35, 40]
             / | \    / | \     / | \
           叶子节点(数据页)通过双向链表连接
```

**B+ 树特点**：

1. **非叶子节点只存索引**：更多的索引可以放入内存
2. **叶子节点存储数据**：数据按顺序存放
3. **叶子节点双向链表**：支持范围查询
4. **树高度低**：通常 3-4 层可存储千万级数据

**为什么不用 B 树？**
- B 树的非叶子节点也存储数据，同样的空间能存储的索引更少
- B 树不适合范围查询，需要中序遍历

**为什么不用 Hash？**
- Hash 不支持范围查询
- Hash 不支持排序
- Hash 存在哈希冲突问题

### 2.2 索引存储

**聚簇索引（Clustered Index）**：
- 数据和索引存储在一起
- InnoDB 的主键索引就是聚簇索引
- 一张表只能有一个聚簇索引

**非聚簇索引（Secondary Index）**：
- 索引和数据分开存储
- 叶子节点存储的是主键值
- 查询需要**回表**（根据主键再查一次）

```
主键索引（聚簇索引）
[id] -> 完整行数据

普通索引（非聚簇索引）
[name] -> 主键id -> 完整行数据（回表）
```

---

## 三、索引类型

### 3.1 按功能分类

| 类型 | 说明 | 示例 |
|------|------|------|
| **主键索引** | 唯一且非空，每表一个 | `PRIMARY KEY (id)` |
| **唯一索引** | 值唯一，可以为 NULL | `UNIQUE KEY idx_email (email)` |
| **普通索引** | 最基本的索引 | `KEY idx_name (name)` |
| **全文索引** | 文本搜索 | `FULLTEXT KEY idx_content (content)` |

### 3.2 按列数分类

**单列索引**：
```sql
CREATE INDEX idx_name ON users(name);
```

**联合索引（复合索引）**：
```sql
CREATE INDEX idx_name_age ON users(name, age);
```

### 3.3 创建索引语法

```sql
-- 创建表时定义
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50),
    email VARCHAR(100) UNIQUE,
    age INT,
    created_at DATETIME,
    INDEX idx_name (name),
    INDEX idx_age_created (age, created_at)
);

-- 单独创建
CREATE INDEX idx_name ON users(name);
CREATE UNIQUE INDEX idx_email ON users(email);

-- 删除索引
DROP INDEX idx_name ON users;

-- 查看索引
SHOW INDEX FROM users;
```

---

## 四、索引设计原则

### 4.1 什么字段应该建索引？

✅ **应该建索引**：

1. **WHERE 子句中的字段**
2. **JOIN 关联字段**
3. **ORDER BY / GROUP BY 字段**
4. **区分度高的字段**（如用户ID、手机号）
5. **频繁查询的字段**

❌ **不应该建索引**：

1. **数据量小的表**（全表扫描可能更快）
2. **频繁更新的字段**（维护索引开销大）
3. **区分度低的字段**（如性别、状态）
4. **TEXT/BLOB 类型**（考虑前缀索引）

### 4.2 索引区分度

```sql
-- 计算索引区分度（选择性）
SELECT 
    COUNT(DISTINCT column_name) / COUNT(*) AS selectivity
FROM table_name;

-- 区分度越接近 1 越好
-- 性别字段区分度约 0.5，不适合单独建索引
-- 手机号区分度接近 1，适合建索引
```

### 4.3 联合索引设计原则

**最左前缀原则**：联合索引 `(a, b, c)` 可以命中以下查询：

| 查询条件 | 是否命中索引 |
|---------|-------------|
| `WHERE a = 1` | ✅ 命中 |
| `WHERE a = 1 AND b = 2` | ✅ 命中 |
| `WHERE a = 1 AND b = 2 AND c = 3` | ✅ 命中 |
| `WHERE b = 2` | ❌ 不命中 |
| `WHERE b = 2 AND c = 3` | ❌ 不命中 |
| `WHERE a = 1 AND c = 3` | ⚠️ 部分命中（只用到 a） |

**设计建议**：

1. **高频字段放前面**
2. **区分度高的字段放前面**
3. **范围查询放后面**（范围查询后的字段无法使用索引）

```sql
-- 好的设计
CREATE INDEX idx_status_type_created ON orders(user_id, status, created_at);

-- 查询：用户的某状态订单，按时间排序
SELECT * FROM orders 
WHERE user_id = 1 AND status = 'PAID' 
ORDER BY created_at DESC;
```

---

## 五、覆盖索引

### 5.1 什么是覆盖索引？

当查询的所有列都包含在索引中时，不需要回表查询，称为**覆盖索引**。

```sql
-- 创建联合索引
CREATE INDEX idx_name_age ON users(name, age);

-- ✅ 覆盖索引：只查询 name 和 age
SELECT name, age FROM users WHERE name = '张三';
-- 直接从索引获取数据，无需回表

-- ❌ 需要回表：查询了 email 字段
SELECT name, age, email FROM users WHERE name = '张三';
-- 需要通过主键回表获取 email
```

### 5.2 如何判断是否使用覆盖索引？

```sql
EXPLAIN SELECT name, age FROM users WHERE name = '张三';
```

查看 `Extra` 列，如果显示 `Using index`，表示使用了覆盖索引。

### 5.3 覆盖索引优化案例

**场景**：分页查询大量数据

```sql
-- ❌ 慢：深度分页，需要扫描大量数据
SELECT * FROM orders 
WHERE user_id = 1 
ORDER BY id DESC 
LIMIT 100000, 10;

-- ✅ 快：先通过覆盖索引获取主键，再关联查询
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders 
    WHERE user_id = 1 
    ORDER BY id DESC 
    LIMIT 100000, 10
) t ON o.id = t.id;
```

---

## 六、索引失效场景

### 6.1 常见索引失效情况

#### 1. 对索引列使用函数或运算

```sql
-- ❌ 索引失效
SELECT * FROM users WHERE YEAR(created_at) = 2024;
SELECT * FROM users WHERE age + 1 = 20;

-- ✅ 改写
SELECT * FROM users WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';
SELECT * FROM users WHERE age = 19;
```

#### 2. 隐式类型转换

```sql
-- phone 是 VARCHAR 类型
-- ❌ 索引失效：数字和字符串比较
SELECT * FROM users WHERE phone = 13800138000;

-- ✅ 正确写法
SELECT * FROM users WHERE phone = '13800138000';
```

#### 3. LIKE 以通配符开头

```sql
-- ❌ 索引失效
SELECT * FROM users WHERE name LIKE '%张';
SELECT * FROM users WHERE name LIKE '%张%';

-- ✅ 可以使用索引
SELECT * FROM users WHERE name LIKE '张%';
```

#### 4. OR 条件未全部建立索引

```sql
-- 假设只有 name 有索引，age 没有
-- ❌ 索引失效
SELECT * FROM users WHERE name = '张三' OR age = 20;

-- ✅ 改写为 UNION
SELECT * FROM users WHERE name = '张三'
UNION
SELECT * FROM users WHERE age = 20;

-- 或者给 age 也建立索引
```

#### 5. NOT IN / NOT EXISTS / !=

```sql
-- ❌ 可能导致索引失效
SELECT * FROM users WHERE status != 1;
SELECT * FROM users WHERE id NOT IN (1, 2, 3);

-- ✅ 尽量用正向条件
SELECT * FROM users WHERE status IN (0, 2, 3);
```

#### 6. 联合索引不满足最左前缀

```sql
-- 索引 idx_a_b_c (a, b, c)
-- ❌ 索引失效
SELECT * FROM t WHERE b = 1;
SELECT * FROM t WHERE c = 1;
SELECT * FROM t WHERE b = 1 AND c = 2;
```

### 6.2 索引失效排查

```sql
-- 使用 EXPLAIN 分析
EXPLAIN SELECT * FROM users WHERE name = '张三';

-- 关注以下字段：
-- type: 访问类型（ALL 表示全表扫描，应避免）
-- key: 实际使用的索引
-- rows: 预估扫描行数
-- Extra: 额外信息
```

**type 访问类型从好到差**：
```
system > const > eq_ref > ref > range > index > ALL
```

---

## 七、EXPLAIN 执行计划

### 7.1 EXPLAIN 字段详解

```sql
EXPLAIN SELECT * FROM users WHERE name = '张三' AND age > 20;
```

| 字段 | 说明 |
|------|------|
| **id** | 查询序号，id 越大优先级越高 |
| **select_type** | 查询类型（SIMPLE/PRIMARY/SUBQUERY） |
| **table** | 查询的表 |
| **type** | 访问类型（重要！） |
| **possible_keys** | 可能使用的索引 |
| **key** | 实际使用的索引 |
| **key_len** | 索引使用的字节数 |
| **ref** | 索引关联的字段 |
| **rows** | 预估扫描行数 |
| **Extra** | 额外信息 |

### 7.2 type 类型详解

| type | 说明 | 性能 |
|------|------|------|
| **const** | 主键或唯一索引等值查询 | 最优 |
| **eq_ref** | 关联查询中使用主键或唯一索引 | 很好 |
| **ref** | 非唯一索引等值查询 | 好 |
| **range** | 索引范围查询 | 一般 |
| **index** | 索引全扫描 | 差 |
| **ALL** | 全表扫描 | 最差 |

### 7.3 Extra 常见值

| Extra | 说明 |
|-------|------|
| **Using index** | 覆盖索引 ✅ |
| **Using where** | 使用 WHERE 过滤 |
| **Using temporary** | 使用临时表 ⚠️ |
| **Using filesort** | 使用文件排序 ⚠️ |
| **Using index condition** | 索引下推（ICP）|

---

## 八、优化案例

### 8.1 案例一：订单查询优化

**场景**：查询用户最近的订单

```sql
-- 原始 SQL
SELECT * FROM orders 
WHERE user_id = 10001 
ORDER BY created_at DESC 
LIMIT 10;

-- 添加联合索引
CREATE INDEX idx_user_created ON orders(user_id, created_at);

-- EXPLAIN 结果
-- type: ref (使用索引)
-- Extra: Using index condition
```

### 8.2 案例二：避免回表

**场景**：统计用户订单数

```sql
-- ❌ 需要回表
SELECT COUNT(*) FROM orders WHERE user_id = 10001;

-- ✅ 覆盖索引
-- 如果 idx_user_created(user_id, created_at) 已存在
SELECT COUNT(*) FROM orders WHERE user_id = 10001;
-- Extra: Using index
```

### 8.3 案例三：分页优化

**场景**：深度分页问题

```sql
-- ❌ 慢查询：LIMIT 100000, 10
SELECT * FROM orders ORDER BY id DESC LIMIT 100000, 10;

-- ✅ 方案一：游标分页
SELECT * FROM orders WHERE id < #{lastId} ORDER BY id DESC LIMIT 10;

-- ✅ 方案二：延迟关联
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders ORDER BY id DESC LIMIT 100000, 10
) t ON o.id = t.id;
```

### 8.4 案例四：前缀索引

**场景**：长字符串字段建索引

```sql
-- URL 字段很长，全字段建索引浪费空间
-- ✅ 使用前缀索引
CREATE INDEX idx_url ON pages(url(50));

-- 确定前缀长度
SELECT 
    COUNT(DISTINCT LEFT(url, 10)) / COUNT(*) AS sel_10,
    COUNT(DISTINCT LEFT(url, 20)) / COUNT(*) AS sel_20,
    COUNT(DISTINCT LEFT(url, 50)) / COUNT(*) AS sel_50
FROM pages;
-- 选择区分度够高的最小长度
```

---

## 九、索引维护

### 9.1 查看索引使用情况

```sql
-- 查看表索引
SHOW INDEX FROM users;

-- 查看索引使用统计（需开启 performance_schema）
SELECT * FROM sys.schema_unused_indexes;
SELECT * FROM sys.schema_redundant_indexes;
```

### 9.2 索引碎片整理

```sql
-- 分析表
ANALYZE TABLE users;

-- 重建索引（会锁表）
ALTER TABLE users ENGINE=InnoDB;

-- 或者
OPTIMIZE TABLE users;
```

### 9.3 定期审查索引

1. **删除未使用的索引**：减少写入开销
2. **删除重复索引**：如同时存在 `(a)` 和 `(a, b)`，`(a)` 是多余的
3. **合并相似索引**：多个单列索引可能合并为联合索引

---

## 十、总结

### 索引优化口诀

```
查询字段建索引，联合索引最左原则
区分度高放前面，范围查询放后面
避免函数和运算，类型转换要小心
LIKE 通配开头废，覆盖索引省回表
深度分页用游标，EXPLAIN 分析不能少
```

### 核心要点

1. **理解 B+ 树结构**：理解为什么索引能加速查询
2. **遵循最左前缀原则**：设计合理的联合索引
3. **避免索引失效**：函数、类型转换、LIKE 等
4. **使用覆盖索引**：减少回表操作
5. **学会 EXPLAIN**：分析执行计划，定位问题

---

> **参考资料**：
> - 《高性能 MySQL》
> - [MySQL 官方文档 - Optimization](https://dev.mysql.com/doc/refman/8.0/en/optimization.html)
