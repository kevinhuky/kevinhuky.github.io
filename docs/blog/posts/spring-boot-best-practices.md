---
title: Spring Boot 最佳实践与常用技巧
description: Spring Boot 开发最佳实践：项目结构、配置管理、异常处理、日志规范与性能优化技巧。
draft: false
authors: [huyi]
date: 2025-07-15
slug: spring-boot-best-practices
categories:
  - Engineering
  - 终生学习
tags:
  - Java
  - Spring Boot
---

本文总结 Spring Boot 开发中的最佳实践，涵盖项目结构、配置管理、异常处理、日志规范、性能优化等方面，帮助开发者构建更健壮、更易维护的应用程序。<!-- more -->

# Spring Boot 最佳实践与常用技巧

## 一、项目结构规范

### 1.1 推荐的包结构

```
com.example.myapp/
├── MyApplication.java          # 启动类
├── config/                     # 配置类
│   ├── WebConfig.java
│   ├── SecurityConfig.java
│   └── SwaggerConfig.java
├── controller/                 # 控制器层
│   └── UserController.java
├── service/                    # 服务层
│   ├── UserService.java
│   └── impl/
│       └── UserServiceImpl.java
├── repository/                 # 数据访问层
│   └── UserRepository.java
├── entity/                     # 实体类
│   └── User.java
├── dto/                        # 数据传输对象
│   ├── request/
│   │   └── UserCreateRequest.java
│   └── response/
│       └── UserResponse.java
├── exception/                  # 自定义异常
│   ├── BusinessException.java
│   └── GlobalExceptionHandler.java
├── util/                       # 工具类
│   └── DateUtils.java
└── constant/                   # 常量类
    └── ErrorCode.java
```

### 1.2 分层职责

| 层级 | 职责 | 命名规范 |
|------|------|---------|
| Controller | 接收请求、参数校验、返回响应 | `*Controller` |
| Service | 业务逻辑处理 | `*Service` / `*ServiceImpl` |
| Repository | 数据访问 | `*Repository` / `*Mapper` |
| Entity | 数据库映射实体 | 与表名对应 |
| DTO | 数据传输对象 | `*Request` / `*Response` |

---

## 二、配置管理

### 2.1 多环境配置

```yaml
# application.yml - 通用配置
spring:
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}  # 默认开发环境

# application-dev.yml - 开发环境
server:
  port: 8080
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb_dev

# application-prod.yml - 生产环境
server:
  port: 80
spring:
  datasource:
    url: jdbc:mysql://prod-db:3306/mydb
```

### 2.2 配置类封装

将配置项封装到类中，便于管理和使用：

```java
@Data
@Component
@ConfigurationProperties(prefix = "app")
public class AppProperties {
    private String name;
    private String version;
    private Security security = new Security();
    
    @Data
    public static class Security {
        private String jwtSecret;
        private long jwtExpiration = 86400000;  // 默认值
    }
}
```

```yaml
# application.yml
app:
  name: MyApplication
  version: 1.0.0
  security:
    jwt-secret: ${JWT_SECRET:default-secret}
    jwt-expiration: 86400000
```

### 2.3 敏感信息处理

**❌ 不要这样做**：
```yaml
spring:
  datasource:
    password: 123456  # 明文密码
```

**✅ 推荐做法**：
```yaml
spring:
  datasource:
    password: ${DB_PASSWORD}  # 从环境变量读取
```

或使用 Jasypt 加密：
```yaml
spring:
  datasource:
    password: ENC(加密后的密码)
```

---

## 三、统一响应格式

### 3.1 定义响应结构

```java
@Data
@AllArgsConstructor
@NoArgsConstructor
public class Result<T> {
    private int code;
    private String message;
    private T data;
    private long timestamp = System.currentTimeMillis();
    
    public static <T> Result<T> success(T data) {
        return new Result<>(200, "success", data, System.currentTimeMillis());
    }
    
    public static <T> Result<T> error(int code, String message) {
        return new Result<>(code, message, null, System.currentTimeMillis());
    }
}
```

### 3.2 Controller 使用

```java
@RestController
@RequestMapping("/api/users")
public class UserController {
    
    @GetMapping("/{id}")
    public Result<UserResponse> getUser(@PathVariable Long id) {
        UserResponse user = userService.getById(id);
        return Result.success(user);
    }
    
    @PostMapping
    public Result<Long> createUser(@Valid @RequestBody UserCreateRequest request) {
        Long userId = userService.create(request);
        return Result.success(userId);
    }
}
```

### 3.3 响应示例

```json
// 成功响应
{
    "code": 200,
    "message": "success",
    "data": {
        "id": 1,
        "username": "zhangsan",
        "email": "zhangsan@example.com"
    },
    "timestamp": 1705123456789
}

// 错误响应
{
    "code": 40001,
    "message": "用户不存在",
    "data": null,
    "timestamp": 1705123456789
}
```

---

## 四、全局异常处理

### 4.1 自定义业务异常

```java
@Getter
public class BusinessException extends RuntimeException {
    private final int code;
    
    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
    }
    
    public BusinessException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.code = errorCode.getCode();
    }
}

// 错误码枚举
@Getter
@AllArgsConstructor
public enum ErrorCode {
    USER_NOT_FOUND(40001, "用户不存在"),
    USER_ALREADY_EXISTS(40002, "用户已存在"),
    INVALID_PASSWORD(40003, "密码错误"),
    UNAUTHORIZED(40100, "未登录或登录已过期"),
    FORBIDDEN(40300, "无权限访问"),
    SYSTEM_ERROR(50000, "系统内部错误");
    
    private final int code;
    private final String message;
}
```

### 4.2 全局异常处理器

```java
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    // 业务异常
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException e) {
        log.warn("业务异常: code={}, message={}", e.getCode(), e.getMessage());
        return Result.error(e.getCode(), e.getMessage());
    }
    
    // 参数校验异常
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .findFirst()
                .orElse("参数校验失败");
        log.warn("参数校验失败: {}", message);
        return Result.error(40000, message);
    }
    
    // 未知异常
    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e) {
        log.error("系统异常", e);
        return Result.error(50000, "系统内部错误，请稍后重试");
    }
}
```

---

## 五、参数校验

### 5.1 常用校验注解

```java
@Data
public class UserCreateRequest {
    @NotBlank(message = "用户名不能为空")
    @Size(min = 2, max = 20, message = "用户名长度应在2-20之间")
    private String username;
    
    @NotBlank(message = "密码不能为空")
    @Pattern(regexp = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)[a-zA-Z\\d]{8,}$",
             message = "密码至少8位，包含大小写字母和数字")
    private String password;
    
    @Email(message = "邮箱格式不正确")
    private String email;
    
    @Min(value = 0, message = "年龄不能为负数")
    @Max(value = 150, message = "年龄不能超过150")
    private Integer age;
    
    @NotNull(message = "手机号不能为空")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;
}
```

### 5.2 分组校验

```java
// 定义校验分组
public interface CreateGroup {}
public interface UpdateGroup {}

@Data
public class UserRequest {
    @Null(groups = CreateGroup.class, message = "创建时不能指定ID")
    @NotNull(groups = UpdateGroup.class, message = "更新时必须指定ID")
    private Long id;
    
    @NotBlank(groups = {CreateGroup.class, UpdateGroup.class})
    private String username;
}

// Controller 中使用
@PostMapping
public Result<Long> create(@Validated(CreateGroup.class) @RequestBody UserRequest request) { }

@PutMapping
public Result<Void> update(@Validated(UpdateGroup.class) @RequestBody UserRequest request) { }
```

---

## 六、日志规范

### 6.1 日志级别使用

| 级别 | 用途 | 示例 |
|------|------|------|
| ERROR | 影响功能使用的错误 | 数据库连接失败、空指针异常 |
| WARN | 潜在问题，但不影响功能 | 配置缺失使用默认值 |
| INFO | 重要业务信息 | 用户登录、订单创建 |
| DEBUG | 调试信息 | 方法入参、SQL 语句 |

### 6.2 日志最佳实践

```java
@Slf4j
@Service
public class UserServiceImpl implements UserService {
    
    @Override
    public UserResponse getById(Long id) {
        log.debug("查询用户, id={}", id);
        
        User user = userRepository.findById(id)
                .orElseThrow(() -> {
                    log.warn("用户不存在, id={}", id);
                    return new BusinessException(ErrorCode.USER_NOT_FOUND);
                });
        
        log.info("查询用户成功, id={}, username={}", id, user.getUsername());
        return convertToResponse(user);
    }
    
    @Override
    public Long create(UserCreateRequest request) {
        // ✅ 使用占位符，避免字符串拼接
        log.info("创建用户, username={}", request.getUsername());
        
        // ❌ 不要这样做
        // log.info("创建用户, username=" + request.getUsername());
        
        // ❌ 不要打印敏感信息
        // log.info("创建用户, password={}", request.getPassword());
    }
}
```

### 6.3 Logback 配置

```xml
<!-- logback-spring.xml -->
<configuration>
    <springProfile name="dev">
        <root level="DEBUG">
            <appender-ref ref="CONSOLE"/>
        </root>
    </springProfile>
    
    <springProfile name="prod">
        <root level="INFO">
            <appender-ref ref="FILE"/>
        </root>
        
        <!-- 异步日志，提升性能 -->
        <appender name="ASYNC" class="ch.qos.logback.classic.AsyncAppender">
            <appender-ref ref="FILE"/>
        </appender>
    </springProfile>
</configuration>
```

---

## 七、常用注解速查

### 7.1 核心注解

| 注解 | 作用 |
|------|------|
| `@SpringBootApplication` | 启动类，包含 @Configuration + @EnableAutoConfiguration + @ComponentScan |
| `@RestController` | @Controller + @ResponseBody |
| `@RequestMapping` | 请求映射 |
| `@Autowired` | 依赖注入（推荐使用构造器注入） |
| `@Value` | 注入配置值 |
| `@ConfigurationProperties` | 配置类绑定 |

### 7.2 Web 相关注解

```java
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor  // Lombok 生成构造器
public class UserController {
    
    private final UserService userService;  // 构造器注入
    
    @GetMapping("/{id}")                           // GET /api/users/{id}
    public Result<User> getById(@PathVariable Long id) { }
    
    @GetMapping                                     // GET /api/users?name=xxx
    public Result<List<User>> list(@RequestParam(required = false) String name) { }
    
    @PostMapping                                    // POST /api/users
    public Result<Long> create(@RequestBody @Valid UserCreateRequest request) { }
    
    @PutMapping("/{id}")                           // PUT /api/users/{id}
    public Result<Void> update(@PathVariable Long id, @RequestBody UserUpdateRequest request) { }
    
    @DeleteMapping("/{id}")                        // DELETE /api/users/{id}
    public Result<Void> delete(@PathVariable Long id) { }
}
```

### 7.3 事务相关

```java
@Service
public class OrderServiceImpl implements OrderService {
    
    // 默认：REQUIRED，遇到 RuntimeException 回滚
    @Transactional
    public void createOrder(OrderRequest request) { }
    
    // 指定回滚异常
    @Transactional(rollbackFor = Exception.class)
    public void createOrderWithCheck(OrderRequest request) throws Exception { }
    
    // 只读事务，用于查询优化
    @Transactional(readOnly = true)
    public OrderResponse getOrder(Long id) { }
    
    // 新事务：挂起当前事务，开启新事务
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void saveLog(String content) { }
}
```

---

## 八、性能优化建议

### 8.1 启动优化

```yaml
spring:
  main:
    lazy-initialization: true  # 延迟初始化 Bean
  jmx:
    enabled: false  # 关闭 JMX

# 使用 -noverify 参数跳过字节码验证
# java -noverify -jar app.jar
```

### 8.2 数据库连接池配置

```yaml
spring:
  datasource:
    hikari:
      minimum-idle: 5           # 最小空闲连接数
      maximum-pool-size: 20     # 最大连接数
      idle-timeout: 300000      # 空闲超时时间(ms)
      max-lifetime: 1800000     # 连接最大存活时间(ms)
      connection-timeout: 30000 # 连接超时时间(ms)
```

### 8.3 缓存使用

```java
@Service
@CacheConfig(cacheNames = "users")
public class UserServiceImpl implements UserService {
    
    @Cacheable(key = "#id")  // 查询时缓存
    public UserResponse getById(Long id) { }
    
    @CachePut(key = "#result.id")  // 更新时刷新缓存
    public UserResponse update(UserUpdateRequest request) { }
    
    @CacheEvict(key = "#id")  // 删除时清除缓存
    public void delete(Long id) { }
    
    @CacheEvict(allEntries = true)  // 清除所有缓存
    public void clearCache() { }
}
```

### 8.4 异步处理

```java
@EnableAsync
@Configuration
public class AsyncConfig {
    @Bean
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-");
        return executor;
    }
}

@Service
public class NotificationService {
    @Async  // 异步执行
    public void sendEmail(String to, String content) {
        // 耗时操作
    }
}
```

---

## 九、安全实践

### 9.1 SQL 注入防护

```java
// ✅ 使用参数化查询
@Query("SELECT u FROM User u WHERE u.username = :username")
User findByUsername(@Param("username") String username);

// ❌ 不要拼接 SQL
@Query("SELECT u FROM User u WHERE u.username = '" + username + "'")  // 危险！
```

### 9.2 XSS 防护

```java
// 使用 HtmlUtils 转义
String safeContent = HtmlUtils.htmlEscape(userInput);

// 或使用 @JsonDeserialize 自动转义
```

### 9.3 接口安全

```java
@RestController
@RequestMapping("/api")
public class ApiController {
    
    // 限流
    @RateLimiter(rate = 10, timeUnit = TimeUnit.SECONDS)
    @GetMapping("/data")
    public Result<Data> getData() { }
    
    // 幂等性（通过 Token 或业务 ID）
    @PostMapping("/orders")
    public Result<Long> createOrder(
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @RequestBody OrderRequest request) { }
}
```

---

## 十、实用技巧

### 10.1 优雅停机

```yaml
server:
  shutdown: graceful  # 开启优雅停机

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # 等待时间
```

### 10.2 健康检查

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
  endpoint:
    health:
      show-details: always
```

### 10.3 自定义 Banner

```
  _____             _    _ _ _
 |  __ \           | |  | (_) |
 | |  | | _____   _| |__| |_| | _____ _ __
 | |  | |/ _ \ \ / /  __  | | |/ / _ \ '__|
 | |__| |  __/\ V /| |  | | |   <  __/ |
 |_____/ \___| \_/ |_|  |_|_|_|\_\___|_|
                                    
 :: Spring Boot ::   (v${spring-boot.version})
 :: Application ::   ${app.name} v${app.version}
```

---

> **参考资料**：
> - [Spring Boot 官方文档](https://docs.spring.io/spring-boot/docs/current/reference/html/)
> - 《Spring Boot 实战》
