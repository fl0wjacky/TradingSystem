# 部署指南

## 系统要求

### 最低配置
- CPU: 2核
- 内存: 4GB
- 存储: 50GB SSD
- 网络: 100Mbps

### 推荐配置
- CPU: 8核
- 内存: 16GB
- 存储: 200GB SSD
- 网络: 1Gbps

### 操作系统
- Ubuntu 20.04 LTS 或更高版本
- CentOS 7/8
- macOS 11+
- Windows Server 2019+

## 快速部署

### 使用 Docker Compose

1. **克隆仓库**
```bash
git clone https://github.com/fl0wjacky/TradingSystem.git
cd TradingSystem
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，配置必要的参数
```

3. **启动服务**
```bash
docker-compose up -d
```

4. **检查状态**
```bash
docker-compose ps
docker-compose logs -f
```

### Docker Compose 配置

```yaml
version: '3.8'

services:
  api:
    image: cbdcat/trading-api:latest
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=postgres
      - REDIS_HOST=redis
    depends_on:
      - postgres
      - redis
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs

  worker:
    image: cbdcat/trading-worker:latest
    environment:
      - DB_HOST=postgres
      - REDIS_HOST=redis
    depends_on:
      - postgres
      - redis
    volumes:
      - ./config:/app/config

  postgres:
    image: postgres:14
    environment:
      - POSTGRES_DB=trading
      - POSTGRES_USER=cbdcat
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl

volumes:
  postgres_data:
  redis_data:
```

## Kubernetes 部署

### 1. 准备 Kubernetes 集群

```bash
# 使用 minikube 进行本地测试
minikube start --cpus=4 --memory=8192

# 或使用云服务商的 K8s 服务
# EKS, GKE, AKS 等
```

### 2. 部署应用

```bash
# 创建命名空间
kubectl create namespace trading-system

# 应用配置
kubectl apply -f k8s/ -n trading-system

# 查看部署状态
kubectl get pods -n trading-system
```

### Kubernetes 配置示例

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: trading-api
  template:
    metadata:
      labels:
        app: trading-api
    spec:
      containers:
      - name: api
        image: cbdcat/trading-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DB_HOST
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: host
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: trading-api
spec:
  selector:
    app: trading-api
  ports:
    - port: 8000
      targetPort: 8000
  type: LoadBalancer
```

## 手动部署

### 1. 安装依赖

```bash
# Python 环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node.js 环境
npm install

# 数据库
sudo apt-get install postgresql postgresql-contrib
sudo apt-get install redis-server
```

### 2. 配置数据库

```sql
-- 创建数据库
CREATE DATABASE trading;
CREATE USER cbdcat WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trading TO cbdcat;

-- 执行迁移
python manage.py migrate
```

### 3. 配置服务

```bash
# 配置 systemd 服务
sudo cp deploy/cbdcat-api.service /etc/systemd/system/
sudo cp deploy/cbdcat-worker.service /etc/systemd/system/

# 启动服务
sudo systemctl enable cbdcat-api
sudo systemctl start cbdcat-api
sudo systemctl enable cbdcat-worker
sudo systemctl start cbdcat-worker
```

## 配置文件

### 主配置文件 (config.yaml)

```yaml
app:
  name: CBD Cat Trading System
  version: 1.0.0
  debug: false
  timezone: Asia/Shanghai

database:
  host: localhost
  port: 5432
  name: trading
  user: cbdcat
  password: ${DB_PASSWORD}
  pool_size: 20

redis:
  host: localhost
  port: 6379
  db: 0
  password: ${REDIS_PASSWORD}

exchange:
  binance:
    api_key: ${BINANCE_API_KEY}
    api_secret: ${BINANCE_API_SECRET}
    testnet: false
  
  okx:
    api_key: ${OKX_API_KEY}
    api_secret: ${OKX_API_SECRET}
    passphrase: ${OKX_PASSPHRASE}

logging:
  level: INFO
  file: /var/log/cbdcat/app.log
  max_size: 100M
  backup_count: 10

security:
  jwt_secret: ${JWT_SECRET}
  api_rate_limit: 1000
  ip_whitelist:
    - 127.0.0.1
    - 10.0.0.0/8
```

## SSL/TLS 配置

### 使用 Let's Encrypt

```bash
# 安装 certbot
sudo apt-get install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 监控配置

### Prometheus 配置

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'trading-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
```

### Grafana Dashboard

导入提供的 Dashboard 模板：
1. 登录 Grafana
2. 导入 `deploy/grafana/dashboard.json`
3. 配置数据源为 Prometheus

## 备份策略

### 数据库备份

```bash
# 自动备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/postgres"
pg_dump -U cbdcat -h localhost trading > $BACKUP_DIR/trading_$DATE.sql
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
```

### 配置备份

```bash
# 备份配置和日志
tar -czf backup_config_$(date +%Y%m%d).tar.gz config/ logs/
```

## 故障排查

### 检查服务状态

```bash
# Docker 部署
docker-compose ps
docker-compose logs api
docker-compose logs worker

# Systemd 部署
systemctl status cbdcat-api
journalctl -u cbdcat-api -f
```

### 常见问题

1. **数据库连接失败**
   - 检查数据库服务是否运行
   - 验证连接参数
   - 检查防火墙规则

2. **API 请求超时**
   - 检查网络连接
   - 查看 API 服务日志
   - 检查负载均衡配置

3. **策略不执行**
   - 检查 Worker 服务状态
   - 查看 Redis 连接
   - 检查策略配置

## 性能优化

### 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_created_at ON orders(created_at);

-- 分区表
CREATE TABLE orders_2024 PARTITION OF orders
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

### Redis 优化

```conf
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
```

### 应用优化

- 启用连接池
- 使用缓存策略
- 异步处理任务
- 负载均衡

## 安全建议

1. **定期更新依赖**
```bash
pip list --outdated
pip install --upgrade -r requirements.txt
```

2. **安全扫描**
```bash
# Python 安全扫描
pip install safety
safety check

# Docker 镜像扫描
docker scan cbdcat/trading-api:latest
```

3. **访问控制**
- 使用 VPN 或 IP 白名单
- 启用双因素认证
- 定期轮换 API 密钥

4. **日志审计**
- 记录所有交易操作
- 监控异常访问
- 定期审查日志

## 升级指南

### 版本升级

```bash
# 备份当前版本
docker-compose down
tar -czf backup_$(date +%Y%m%d).tar.gz .

# 拉取新版本
git pull origin main
docker-compose pull

# 执行迁移
docker-compose run api python manage.py migrate

# 启动新版本
docker-compose up -d
```

### 回滚步骤

```bash
# 停止服务
docker-compose down

# 恢复备份
tar -xzf backup_YYYYMMDD.tar.gz

# 启动旧版本
docker-compose up -d
```