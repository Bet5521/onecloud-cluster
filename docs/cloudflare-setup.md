# Cloudflare Zero Trust Tunnel 配置指南

> 使用 Cloudflare Tunnel (cloudflared) 将家庭服务安全暴露到公网，无需公网 IP

## 前置条件

1. Cloudflare 账号（免费版即可）
2. 一个已在 Cloudflare DNS 托管的域名
3. NODE-01 (wk-edge-01) 已完成 bootstrap

---

## 步骤 1: 创建 Tunnel

1. 访问 [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. Networks → Tunnels → Create tunnel
3. 选择 Cloudflared，命名 `onecloud-cluster`
4. 复制 Token（类似 `eyJhIjoi...`）

## 步骤 2: 配置 .env

```bash
ssh root@192.168.1.101
cd /mnt/sd/edge-01
vi .env
# CF_TUNNEL_TOKEN=eyJhIjoiYOUR_REAL_TOKEN_HERE...
```

## 步骤 3: 配置 ingress 路由

`cloudflared/config.yml`:
```yaml
tunnel: onecloud-cluster
credentials-file: /root/.cloudflared/onecloud-cluster.json

ingress:
  - hostname: panel.${DOMAIN}
    service: http://localhost:9000
  - hostname: dns.${DOMAIN}
    service: http://localhost:3000
  - hostname: memos.${DOMAIN}
    service: http://localhost:5230
  - hostname: home.${DOMAIN}
    service: http://192.168.1.102:8123
  - hostname: photos.${DOMAIN}
    service: http://192.168.1.102:8080
  - service: http_status:404
```

## 步骤 4: 创建 DNS 记录

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | adguard | *.cfargotunnel.com | ✅ |
| CNAME | memos | *.cfargotunnel.com | ✅ |
| CNAME | panel | *.cfargotunnel.com | ✅ |
| CNAME | ha | *.cfargotunnel.com | ✅ |
| CNAME | piwigo | *.cfargotunnel.com | ✅ |

## 步骤 5: 启动 Tunnel

```bash
cd /mnt/sd/edge-01
docker-compose up -d cloudflared
docker logs -f cloudflared
```

## 步骤 6: 配置 Access Policy（推荐）

为敏感服务添加身份验证：
1. Zero Trust → Access → Applications → Add an application → Self-hosted
2. Subdomain + Domain
3. Policy: Allow → Emails ending in @yourdomain.com

## 故障排查

### Tunnel 显示 Connection refused
```bash
docker ps | grep cloudflared
curl http://localhost:3000
wg show
```

### Tunnel token 过期
1. Zero Trust → Tunnels → 编辑 tunnel → 重新生成 token
2. 更新 `.env` 中的 CF_TUNNEL_TOKEN
3. `docker-compose up -d cloudflared`

## 安全最佳实践

1. 不要把 token 提交到 git（`.env` 已加入 `.gitignore`）
2. 定期轮换 token（每月）
3. 启用 Access Policy（至少对 Panel 和 AdGuard）
4. 在 Access → Logs 查看访问记录
5. 在 Tunnel 设置中强制 HTTPS
