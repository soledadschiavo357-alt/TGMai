/**
 * Cloudflare Worker Soft Router Reference Implementation
 * 包含：流量转发、负载均衡、HTTPS强制、缓存策略、安全防护
 */

// 后端服务器列表 (用于负载均衡)
const BACKENDS = [
  "https://server1.example.com",
  "https://server2.example.com",
  "https://server3.example.com"
];

// 安全头配置
const SECURITY_HEADERS = {
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-XSS-Protection": "1; mode=block",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Content-Security-Policy": "default-src 'self' https:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:;"
};

// 简单的黑名单 IP (示例)
const BLOCKED_IPS = ["1.2.3.4", "5.6.7.8"];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const clientIP = request.headers.get("CF-Connecting-IP");

    // 1. 安全防护：IP 黑名单检查
    if (BLOCKED_IPS.includes(clientIP)) {
      return new Response("Access Denied", { status: 403 });
    }

    // 2. 协议强制：强制 HTTPS
    if (url.protocol === "http:") {
      url.protocol = "https:";
      return Response.redirect(url.toString(), 301);
    }

    // 3. 流量转发与负载均衡
    // 简单策略：随机选择后端 (Round Robin 可以通过 KV 或 Durable Objects 实现更复杂状态)
    const backend = BACKENDS[Math.floor(Math.random() * BACKENDS.length)];
    
    // 构建新的请求 URL
    // 假设我们要把所有 /api/* 的请求转发到后端
    if (url.pathname.startsWith("/api")) {
      const newUrl = new URL(url.pathname + url.search, backend);
      
      // 创建新的请求对象 (修改 Host 头以匹配后端)
      const newRequest = new Request(newUrl, request);
      newRequest.headers.set("Host", newUrl.hostname);

      // 4. 发起请求
      try {
        let response = await fetch(newRequest);

        // 5. 缓存策略 (对特定资源)
        // 重新构建响应以修改 Header
        response = new Response(response.body, response);

        // 为静态资源添加缓存头
        if (url.pathname.match(/\.(jpg|png|css|js)$/)) {
           response.headers.set("Cache-Control", "public, max-age=86400");
        }

        // 6. 添加安全响应头
        for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
          response.headers.set(key, value);
        }

        return response;

      } catch (e) {
        return new Response("Backend Unavailable", { status: 502 });
      }
    }

    // 7. 默认行为 (如果不是 API 请求，可以返回 404 或静态内容)
    // 这里演示返回简单的 HTML
    return new Response(`
      <!DOCTYPE html>
      <html>
      <head><title>Soft Router Gateway</title></head>
      <body>
        <h1>Gateway Active</h1>
        <p>Your IP: ${clientIP}</p>
        <p>Routing to: ${backend}</p>
      </body>
      </html>
    `, {
      headers: { 
        "content-type": "text/html;charset=UTF-8",
        ...SECURITY_HEADERS 
      }
    });
  }
};
