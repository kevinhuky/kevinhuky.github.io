---
title: Java 并发编程完全指南
description: 系统总结 Java 并发编程核心：锁机制、CAS、AQS、线程池与并发容器，深入理解 JUC 的设计思想与实战应用。
draft: false
authors: [huyi]
date: 2024-09-12
slug: juc
categories:
  - Engineering
  - 终生学习
tags:
  - Java
  - 并发编程
---

本文系统总结 Java 并发编程的核心知识点，包括锁机制、CAS、AQS、线程池、并发容器等，帮助深入理解 JUC 包的设计思想与实战应用。<!-- more -->

# Java 并发编程完全指南

## 一、并发基础概念

### 1.1 为什么需要并发？

- **充分利用多核 CPU**：现代 CPU 都是多核心，并发编程能充分发挥硬件性能
- **提高系统吞吐量**：通过并行处理提升整体处理能力
- **改善用户体验**：异步处理避免界面卡顿

### 1.2 并发带来的问题

| 问题 | 描述 | 示例 |
|------|------|------|
| **原子性** | 一个操作不可被中断 | i++ 不是原子操作 |
| **可见性** | 一个线程的修改对其他线程可见 | 缓存导致读取旧值 |
| **有序性** | 程序按代码顺序执行 | 指令重排序 |

---

## 二、乐观锁与悲观锁

现实生活中，有资源就有竞争，我认为锁就是对有限资源的一种争取；程序中的锁也是一样，对共享资源（内容）进行操作，需要保证操作的安全性，即保证共享资源的完整性和一致性。

### 2.1 悲观锁

**思想**：认为共享资源每次访问时都会有问题，所以**每次获取数据都需要加锁（独享）**，直到自己操作完成后释放锁之后，其他线程才可以进行操作。

**Java 实现**：`synchronized` 和 `ReentrantLock`

```java
// synchronized 示例
public synchronized void increment() {
    count++;
}

// ReentrantLock 示例
private final ReentrantLock lock = new ReentrantLock();
public void increment() {
    lock.lock();
    try {
        count++;
    } finally {
        lock.unlock();
    }
}
```

### 2.2 乐观锁

**思想**：认为共享资源每次访问的时候都不会出问题，不需要加锁，只需要**在提交修改时再判断对应的资源是否符合预期**。

**实现方式**：
- **版本号机制**：数据表增加 version 字段
- **CAS 算法**：Compare And Swap

```java
// 乐观锁 - 版本号机制（数据库）
UPDATE account SET balance = balance - 100, version = version + 1 
WHERE id = 1 AND version = #{oldVersion}

// 乐观锁 - CAS（Java）
AtomicInteger count = new AtomicInteger(0);
count.incrementAndGet();  // 内部使用 CAS
```

### 2.3 如何选择？

| 场景 | 推荐 | 原因 |
|------|------|------|
| 读多写少 | 乐观锁 | 冲突少，无锁开销小 |
| 写多读少 | 悲观锁 | 冲突多，CAS 自旋消耗 CPU |
| 临界区执行时间长 | 悲观锁 | 避免长时间自旋 |

---

## 三、CAS 深入解析

### 3.1 什么是 CAS？

**CAS（Compare And Swap）** 是一种**无锁的原子性操作**，包含三个操作数：

- **V**（内存位置）：要更新的变量
- **A**（期望值）：预期的原值
- **B**（新值）：要设置的新值

**工作原理**：当且仅当 V 的值等于 A 时，将 V 的值更新为 B，否则不做任何操作。整个过程是原子的。

```
if (V == A) {
    V = B;
    return true;
} else {
    return false;
}
```

### 3.2 Java 中的 CAS

`java.util.concurrent.atomic` 包提供了一系列原子类：

```java
// AtomicInteger 示例
AtomicInteger atomicInt = new AtomicInteger(0);

atomicInt.get();                    // 获取当前值
atomicInt.incrementAndGet();        // 自增并返回新值
atomicInt.compareAndSet(0, 1);      // CAS 操作

// AtomicReference 示例 - 原子更新引用类型
AtomicReference<User> atomicUser = new AtomicReference<>();
atomicUser.compareAndSet(oldUser, newUser);
```

**底层实现**：通过 `Unsafe` 类的 native 方法调用 CPU 的 CAS 指令（如 x86 的 `CMPXCHG`）。

### 3.3 CAS 的问题与解决

#### ABA 问题

**问题**：线程 1 读取值为 A，线程 2 将 A 改为 B 再改回 A，线程 1 的 CAS 仍然成功。

**解决**：使用 `AtomicStampedReference`，增加版本号。

```java
AtomicStampedReference<Integer> atomicRef = new AtomicStampedReference<>(1, 0);

int stamp = atomicRef.getStamp();  // 获取版本号
atomicRef.compareAndSet(1, 2, stamp, stamp + 1);  // 同时比较值和版本号
```

#### 自旋开销

**问题**：CAS 失败会不断重试，高并发时 CPU 开销大。

**解决**：
- 使用 `LongAdder` 代替 `AtomicLong`（分段 CAS）
- 适当退避策略

```java
// LongAdder 适合高并发计数场景
LongAdder adder = new LongAdder();
adder.increment();
adder.sum();  // 获取总和
```

---

## 四、synchronized 关键字

### 4.1 三种使用方式

```java
public class SyncDemo {
    // 1. 修饰实例方法 - 锁当前实例对象
    public synchronized void method1() { }
    
    // 2. 修饰静态方法 - 锁当前类的 Class 对象
    public static synchronized void method2() { }
    
    // 3. 修饰代码块 - 锁指定对象
    public void method3() {
        synchronized (this) { }       // 锁当前实例
        synchronized (SyncDemo.class) { }  // 锁 Class 对象
    }
}
```

### 4.2 锁升级过程（JDK 6+）

```
无锁 → 偏向锁 → 轻量级锁 → 重量级锁
```

| 锁状态 | 适用场景 | 特点 |
|--------|---------|------|
| **偏向锁** | 单线程访问 | 无竞争时几乎无开销 |
| **轻量级锁** | 少量线程交替访问 | CAS 自旋获取锁 |
| **重量级锁** | 多线程竞争激烈 | 阻塞等待，涉及内核态切换 |

### 4.3 synchronized vs ReentrantLock

| 特性 | synchronized | ReentrantLock |
|------|-------------|---------------|
| 实现 | JVM 内置 | JDK 实现 |
| 释放锁 | 自动释放 | 需手动 unlock |
| 可中断 | 不支持 | 支持 `lockInterruptibly()` |
| 超时获取 | 不支持 | 支持 `tryLock(timeout)` |
| 公平锁 | 非公平 | 可选公平/非公平 |
| 条件变量 | 单一 | 支持多个 Condition |

---

## 五、AQS（AbstractQueuedSynchronizer）

### 5.1 什么是 AQS？

AQS 是 JUC 包中**锁和同步器的基础框架**，`ReentrantLock`、`Semaphore`、`CountDownLatch` 等都基于它实现。

### 5.2 核心原理

```
┌─────────────────────────────────────────────┐
│                    AQS                       │
│  ┌─────────────────────────────────────┐    │
│  │     state (volatile int)            │    │
│  │     0 = 未锁定, >0 = 已锁定/重入次数  │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │     CLH 队列（双向链表）              │    │
│  │  head ←→ Node1 ←→ Node2 ←→ tail    │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

- **state**：同步状态，通过 CAS 修改
- **CLH 队列**：存放等待获取锁的线程

### 5.3 独占锁获取流程

```java
// 获取锁流程（简化）
public final void acquire(int arg) {
    if (!tryAcquire(arg) &&                    // 1. 尝试获取锁
        acquireQueued(addWaiter(Node.EXCLUSIVE), arg))  // 2. 失败则入队等待
        selfInterrupt();
}
```

1. 调用 `tryAcquire()` 尝试获取锁（由子类实现）
2. 获取失败则创建节点加入 CLH 队列
3. 在队列中自旋等待前驱节点释放锁

---

## 六、线程池详解

### 6.1 为什么需要线程池？

> 线程的频繁创建与销毁代价很高，类似于 TCP 连接的频繁创建与销毁

**好处**：
- **降低资源消耗**：重复利用已创建的线程
- **提高响应速度**：任务到达时无需等待线程创建
- **提高可管理性**：统一分配、调优和监控

### 6.2 核心参数

```java
public ThreadPoolExecutor(
    int corePoolSize,      // 核心线程数
    int maximumPoolSize,   // 最大线程数
    long keepAliveTime,    // 非核心线程空闲存活时间
    TimeUnit unit,         // 时间单位
    BlockingQueue<Runnable> workQueue,  // 任务队列
    ThreadFactory threadFactory,         // 线程工厂
    RejectedExecutionHandler handler     // 拒绝策略
)
```

### 6.3 工作流程

```
                    提交任务
                       │
                       ▼
        ┌──────────────────────────┐
        │  当前线程数 < corePoolSize?│
        └──────────────────────────┘
                 │Yes        │No
                 ▼           ▼
           创建核心线程   ┌─────────────┐
           执行任务      │ 任务队列已满? │
                        └─────────────┘
                          │No      │Yes
                          ▼        ▼
                      加入队列  ┌─────────────────┐
                              │线程数<maximumPool?│
                              └─────────────────┘
                                │Yes       │No
                                ▼          ▼
                          创建非核心线程  执行拒绝策略
```

### 6.4 四种拒绝策略

| 策略 | 行为 |
|------|------|
| **AbortPolicy** | 抛出 RejectedExecutionException（默认） |
| **CallerRunsPolicy** | 由调用线程执行任务 |
| **DiscardPolicy** | 静默丢弃任务 |
| **DiscardOldestPolicy** | 丢弃队列中最老的任务 |

### 6.5 常用线程池（不推荐直接使用）

```java
// ❌ 不推荐：可能导致 OOM
Executors.newFixedThreadPool(10);    // 无界队列
Executors.newCachedThreadPool();     // 无限创建线程
Executors.newSingleThreadExecutor(); // 无界队列

// ✅ 推荐：手动创建，明确参数
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    10,                          // 核心线程数
    20,                          // 最大线程数
    60, TimeUnit.SECONDS,        // 空闲时间
    new ArrayBlockingQueue<>(100), // 有界队列
    new ThreadPoolExecutor.CallerRunsPolicy()  // 拒绝策略
);
```

### 6.6 参数配置建议

| 任务类型 | corePoolSize | 队列 |
|---------|--------------|------|
| **CPU 密集型** | CPU 核心数 + 1 | 较小队列 |
| **IO 密集型** | CPU 核心数 × 2 | 较大队列 |
| **混合型** | 根据实际测试调整 | - |

---

## 七、并发工具类

### 7.1 CountDownLatch（倒计时器）

等待多个线程完成后再继续执行。

```java
CountDownLatch latch = new CountDownLatch(3);

// 工作线程
for (int i = 0; i < 3; i++) {
    new Thread(() -> {
        // 执行任务
        latch.countDown();  // 计数减 1
    }).start();
}

latch.await();  // 阻塞等待计数归零
System.out.println("所有任务完成");
```

### 7.2 CyclicBarrier（循环栅栏）

让一组线程到达屏障点后同时继续执行，可重复使用。

```java
CyclicBarrier barrier = new CyclicBarrier(3, () -> {
    System.out.println("所有线程到达屏障");
});

for (int i = 0; i < 3; i++) {
    new Thread(() -> {
        System.out.println(Thread.currentThread().getName() + " 到达");
        barrier.await();  // 等待其他线程
        System.out.println(Thread.currentThread().getName() + " 继续执行");
    }).start();
}
```

### 7.3 Semaphore（信号量）

控制同时访问资源的线程数量。

```java
// 限制最多 3 个线程同时访问
Semaphore semaphore = new Semaphore(3);

for (int i = 0; i < 10; i++) {
    new Thread(() -> {
        try {
            semaphore.acquire();  // 获取许可
            System.out.println(Thread.currentThread().getName() + " 执行");
            Thread.sleep(1000);
        } finally {
            semaphore.release();  // 释放许可
        }
    }).start();
}
```

### 7.4 对比总结

| 工具 | 用途 | 是否可重用 |
|------|------|-----------|
| CountDownLatch | 等待多个线程完成 | ❌ 一次性 |
| CyclicBarrier | 多线程互相等待 | ✅ 可重用 |
| Semaphore | 控制并发数量 | ✅ 可重用 |

---

## 八、并发容器

### 8.1 ConcurrentHashMap

线程安全的 HashMap，JDK 8 采用 **CAS + synchronized** 实现。

```java
ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
map.put("key", 1);
map.computeIfAbsent("key2", k -> 2);  // 原子操作
```

**JDK 7 vs JDK 8**：

| 版本 | 实现方式 | 锁粒度 |
|------|---------|-------|
| JDK 7 | 分段锁（Segment） | 段级别 |
| JDK 8 | CAS + synchronized | Node 级别 |

### 8.2 CopyOnWriteArrayList

适合**读多写少**场景的线程安全 List。

```java
CopyOnWriteArrayList<String> list = new CopyOnWriteArrayList<>();
list.add("item");  // 写时复制整个数组
```

**原理**：写操作时复制整个数组，读操作无锁。

### 8.3 BlockingQueue

阻塞队列，常用于生产者-消费者模式。

| 实现类 | 特点 |
|--------|------|
| ArrayBlockingQueue | 有界数组队列 |
| LinkedBlockingQueue | 可选有界链表队列 |
| PriorityBlockingQueue | 无界优先级队列 |
| SynchronousQueue | 不存储元素，直接传递 |

```java
BlockingQueue<String> queue = new ArrayBlockingQueue<>(10);

// 生产者
queue.put("item");      // 队列满时阻塞

// 消费者
String item = queue.take();  // 队列空时阻塞
```

---

## 九、volatile 关键字

### 9.1 两大特性

1. **可见性**：一个线程修改后，其他线程立即可见
2. **禁止指令重排序**：通过内存屏障实现

### 9.2 典型应用

```java
// 单例模式 - 双重检查锁定
public class Singleton {
    private static volatile Singleton instance;  // 必须加 volatile
    
    public static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();  // 防止指令重排
                }
            }
        }
        return instance;
    }
}
```

### 9.3 volatile vs synchronized

| 特性 | volatile | synchronized |
|------|----------|--------------|
| 原子性 | ❌ 不保证 | ✅ 保证 |
| 可见性 | ✅ 保证 | ✅ 保证 |
| 有序性 | ✅ 保证 | ✅ 保证 |
| 阻塞 | ❌ 不阻塞 | ✅ 阻塞 |

---

## 十、最佳实践

### 10.1 并发编程原则

1. **不可变优先**：尽量使用不可变对象
2. **最小化锁范围**：只在必要的代码块加锁
3. **避免死锁**：按固定顺序获取多个锁
4. **使用并发工具**：优先使用 JUC 包中的工具类

### 10.2 常见问题排查

```java
// 死锁检测
jstack <pid>  // 查看线程堆栈

// 线程池监控
executor.getActiveCount();     // 活跃线程数
executor.getQueue().size();    // 队列任务数
executor.getCompletedTaskCount();  // 已完成任务数
```

---

> **参考资料**：
> - 《Java 并发编程实战》
> - 《Java 并发编程的艺术》