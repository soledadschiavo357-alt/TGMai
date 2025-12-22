# Cloudflare Soft Router Reference

这是一个基于 Cloudflare Workers 实现的软路由（网关）参考配置。

## 功能特性

1. **流量转发 (Reverse Proxy)**
   - 将 `/api/*` 请求转发到后端服务器集群。
   
2. **负载均衡 (Load Balancing)**
   - 演示了简单的 Round Robin（随机）策略，在多个后端服务器之间分发请求。

3. **安全防护 (Security)**
   - **IP 黑名单**：拦截特定 IP。
   - **HTTPS 强制**：自动将 HTTP 重定向到 HTTPS。
   - **安全响应头**：自动添加 HSTS, CSP, X-Frame-Options 等安全头。

4. **缓存策略 (Caching)**
   - 针对静态资源 (.jpg, .png, .css, .js) 设置缓存头。

## 部署说明

### 1. 安装 Wrangler CLI

```bash
npm install -g wrangler
```

### 2. 本地开发测试

```bash
cd soft-router-reference
wrangler dev
```

### 3. 部署到 Cloudflare

```bash
wrangler deploy
```

## 配置修改

修改 `src/worker.js` 中的常量配置：

- `BACKENDS`: 后端服务器列表。
- `BLOCKED_IPS`: 要屏蔽的 IP 列表。
- `SECURITY_HEADERS`: 自定义安全头。
