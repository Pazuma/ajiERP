# Frappe 开发容器停止问题处理记录

## 现象

执行 `docker exec` 进入 `devcontainer-frappe-1` 时出现 `container ... is not running`。

## 诊断结果

使用以下命令检查：

```bash
docker ps -a --filter name=devcontainer-frappe-1
docker inspect devcontainer-frappe-1 --format 'Status={{.State.Status}} ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}} Error={{.State.Error}}'
docker logs --tail 100 devcontainer-frappe-1
```

本次结果为：容器 `Exited`，退出码 `143`，日志出现 `SIGTERM received`，并且 `OOMKilled=false`。这表示容器收到停止信号后正常退出，不是 Frappe 站点崩溃，也不是内存不足。

## 恢复容器

开发容器使用 `.devcontainer/docker-compose.yml`，应在仓库根目录执行：

```bash
cd ~/frappe_docker
docker compose -f .devcontainer/docker-compose.yml up -d
docker compose -f .devcontainer/docker-compose.yml ps
```

如果修改过 Compose 配置，执行：

```bash
docker compose -f .devcontainer/docker-compose.yml up -d --force-recreate frappe
```

## 端口和启动方式

容器启动命令是 `bench start`，已经包含 Web、SocketIO、队列和调度器，并监听 `8300`。容器正常运行时，不要再启动第二个 `bench serve --port 8300`，避免端口冲突。

访问地址：

```text
http://aki_test.localhost:8300
```

验证：

```bash
curl -I -H 'Host: aki_test.localhost' http://127.0.0.1:8300/
```

## 关闭自动重启

`frappe` 服务已设置为：

```yaml
restart: "no"
```

修改后必须重建服务：

```bash
docker compose -f .devcontainer/docker-compose.yml up -d --force-recreate frappe
docker inspect devcontainer-frappe-1 --format 'RestartPolicy={{.HostConfig.RestartPolicy.Name}}'
```

输出为空或 `no` 即表示不会自动重启。

## 注意事项

1. 开发环境使用 `.devcontainer/docker-compose.yml`，不要混用根目录的 `compose.yaml`。
2. 根目录 Compose 依赖 `ERPNEXT_VERSION`；未设置时可能生成 `frappe/erpnext:` 并报 `invalid reference format`。
3. 关闭 `frappe` 自动重启后，主机重启或容器停止时需要手动执行 `docker compose ... up -d`。
4. 本次只关闭了 `frappe` 的自动重启，MariaDB、Redis 和 OCR 服务保留原有策略。

## 快速处理

```bash
cd ~/frappe_docker
docker compose -f .devcontainer/docker-compose.yml up -d
docker logs --tail 50 devcontainer-frappe-1
curl -I -H 'Host: aki_test.localhost' http://127.0.0.1:8300/
```
