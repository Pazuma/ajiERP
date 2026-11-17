# Windows Server 本地离线部署手册

本文用于将当前 ajiERP（Frappe / ERPNext `v16.32.0`）部署到客户的 Windows 服务器。目标是即使客户 WiFi 没有公网访问能力，也可以从 U 盘完成安装、恢复数据和上线验证。

## 1. 部署架构

Windows Server 不能安装 Docker Desktop。Mirantis Container Runtime（MCR）是 Windows Server 的受支持容器运行时，但其原生目标是 **Windows 容器**；本项目的 ERPNext、MariaDB、Redis 镜像均为 **Linux 容器**，因此不能直接用 MCR 在 Windows 主机上运行。

推荐使用以下架构：

```text
客户 Windows Server
  └─ Hyper-V
      └─ Ubuntu Server 24.04 LTS 虚拟机
          └─ Docker Engine + Docker Compose
              └─ ERPNext / MariaDB / Redis 容器
```

优点是 Docker、数据库、备份和日常运维均在 Linux 环境中完成，和本项目的官方编排一致。Windows Server 只负责提供虚拟化、网络和磁盘。

> MCR 仅在该 Windows Server 还需要运行其他 Windows 容器时安装。本 ERPNext 部署不需要 MCR；Docker Engine 和 Docker Compose 安装在 Ubuntu 虚拟机中。若客户电脑其实是 Windows 10/11 Pro，而非 Windows Server，也仍建议优先使用 Hyper-V Ubuntu 虚拟机。

## 2. 服务器资源规划

服务器规格：AMD EPYC 4124P（4 核）/ 16 GB 内存 / 512 GB SSD。

建议为 Ubuntu 虚拟机分配：

| 资源 | 建议值 | 说明 |
| --- | --- | --- |
| CPU | 3 个 vCPU | 给 Windows 主机保留资源；不要超过物理 4 核。 |
| 内存 | 10-12 GB 固定内存 | ERPNext、MariaDB、Redis、后台任务共用。 |
| 磁盘 | 350 GB 动态 VHDX | 数据库、附件、镜像和日志均在此处增长。 |
| 网卡 | 外部虚拟交换机 | 使 VM 取得客户局域网独立 IP。 |

适用于单站点、轻到中等并发业务。大量 Excel 导入、PDF 打印、复杂库存报表或多人同时使用会增加资源压力，应上线后观察再扩容。

## 3. U 盘离线部署包

使用容量至少 64 GB 的 U 盘，并格式化为 **exFAT**。不要使用 FAT32，Docker 镜像导出文件可能超过 4 GB。

U 盘目录建议如下：

```text
ajierp-offline/
  README.txt
  iso/
    ubuntu-24.04.*-live-server-amd64.iso
  project/
    frappe_docker/                 # 当前项目完整目录
  docker-images/
    ajierp-images-v16.32.0.tar
  docker-debs/
    containerd.io_*.deb
    docker-ce-cli_*.deb
    docker-ce_*.deb
    docker-buildx-plugin_*.deb
    docker-compose-plugin_*.deb
    dependencies/                  # 在同版本 Ubuntu 测试后补齐的依赖包
  config/
    .env                            # 生产配置；不要提交到 Git
    docker-compose.yml              # 已生成的生产编排
    deployment-notes.txt            # 客户网络、域名、账号和现场记录
  backup/
    <site-name>/                    # SQL、public-files、private-files
  custom-apps/                      # 仅存在自定义 App 时需要
```

## 4. 当前电脑必须准备的文件

### 4.1 项目与生产配置

复制当前项目目录到 `project/frappe_docker/`。生产配置必须独立于源码保存：

```bash
cd /home/cst/frappe_docker
cp example.env /path/to/USB/ajierp-offline/config/.env
```

编辑 `.env`，至少修改：

```env
ERPNEXT_VERSION=v16.32.0
DB_PASSWORD=替换为随机高强度数据库密码
GUNICORN_THREADS=4
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120
```

不要使用示例配置中的 `DB_PASSWORD=123`。数据库密码、ERP 管理员密码、SMTP 授权码须记录在客户授权的密码管理工具或加密文档中，不能写入 Git 仓库。

### 4.2 Docker 离线镜像

当前局域网直连方案需要以下镜像：

```text
frappe/erpnext:v16.32.0
mariadb:11.8
redis:8.6-alpine
```

在当前可联网电脑执行：

```bash
docker pull frappe/erpnext:v16.32.0
docker pull mariadb:11.8
docker pull redis:8.6-alpine

docker save -o /path/to/USB/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar \
  frappe/erpnext:v16.32.0 \
  mariadb:11.8 \
  redis:8.6-alpine
```

若启用公网 HTTPS，再加入 `traefik:v3.6`：

```bash
docker pull traefik:v3.6
docker save -o /path/to/USB/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar \
  frappe/erpnext:v16.32.0 \
  mariadb:11.8 \
  redis:8.6-alpine \
  traefik:v3.6
```

每次重新导出前都应在当前电脑导入并检查一次，确认 U 盘文件未损坏：

```bash
docker load -i /path/to/USB/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar
docker image inspect frappe/erpnext:v16.32.0 mariadb:11.8 redis:8.6-alpine
```

### 4.3 Docker 离线安装包

针对 **Ubuntu 24.04 amd64** 准备 Docker Engine 的 `.deb` 安装包：

```text
containerd.io
docker-ce-cli
docker-ce
docker-buildx-plugin
docker-compose-plugin
```

将上述包及其依赖包放入 `docker-debs/`。最可靠的做法是在另一台全新的 Ubuntu 24.04 amd64 测试虚拟机中断网安装一次，缺哪个依赖就补哪个；不要等到客户现场才发现安装依赖缺失。

> 本 ERPNext 部署不使用 Docker Desktop，也不需要 MCR 安装包；需要准备的是 Ubuntu 虚拟机内 Docker Engine 的离线 `.deb` 包。若客户另有 Windows 容器工作负载，则按其 Windows Server 版本和 MCR 授权要求单独准备 MCR。

### 4.4 现网数据与定制

如果是迁移已有站点，必须在旧服务器导出完整备份，而不是新建空站点后重新录入数据：

```bash
docker compose -p <旧项目名> exec backend \
  bench --site <旧站点名> backup --with-files

docker compose -p <旧项目名> exec backend \
  bench --site <旧站点名> version

docker compose -p <旧项目名> exec backend \
  bench --site <旧站点名> list-apps
```

备份目录中应有：数据库 SQL 备份、`public-files`、`private-files`。`version` 和 `list-apps` 的输出保存为文本文件。

如果 `list-apps` 出现任何非 `frappe`、`erpnext` 的 App，必须同时准备：

1. 自定义 App 的源码、私有 Git 凭据或已构建镜像。
2. 与旧站点一致的 App 版本或 Git 提交号。
3. 包含该 App 的 Docker 镜像和 `CUSTOM_IMAGE`、`CUSTOM_TAG` 配置。

只有 Custom Field、Workflow、Print Format、角色权限等数据库配置时，完整站点备份即可恢复；安装了自定义 App 时，仅恢复数据库会导致站点报错。

## 5. 客户现场前必须确认的信息

将以下信息写入 `config/deployment-notes.txt`：

- Windows Server 版本、管理员账号、BIOS 是否已启用虚拟化（AMD-V）。
- 服务器固定 IP、子网掩码、网关、DNS 服务器。
- 是否允许接入有线业务网络；不要依赖可能启用客户端隔离的访客 WiFi。
- 站点访问方式：`http://IP:8080`、内部域名，或公网域名。
- 内部 DNS 是否由客户 IT 添加记录，例如 `erp.company.local -> VM_IP`。
- 公网 HTTPS 时，域名 DNS、80/443 入站端口、证书通知邮箱。
- SMTP 地址、端口、账号和授权码；无 SMTP 时邮件通知不能验证。
- 需要导入的 Excel、附件、报表模板、打印机/扫码设备信息。
- 远程维护方式：SSH、VPN、Windows 远程桌面和客户授权范围。
- 只能通过客户 WiFi 访问的资料地址、登录账号及下载步骤。

客户 WiFi 只能访问的资料不应成为基础安装的依赖。现场连网后再下载资料、导入和验收；Docker、项目、备份和安装包必须已在 U 盘中。

## 6. 现场部署步骤

### 6.1 Windows Server：启用 Hyper-V 并创建虚拟机

以管理员 PowerShell 执行：

```powershell
Install-WindowsFeature -Name Hyper-V -IncludeManagementTools -Restart
```

重启后，在 Hyper-V 管理器中：

1. 创建“外部”虚拟交换机，绑定客户业务网卡。
2. 使用 U 盘的 Ubuntu ISO 创建 Generation 2 虚拟机。
3. 设置 3 vCPU、10-12 GB 固定内存、350 GB 动态 VHDX、外部虚拟交换机。
4. 安装 Ubuntu Server 24.04 LTS，创建专用运维账号。
5. 在 Ubuntu 中设置静态 IP、时区 `Asia/Shanghai`，测试能访问客户内部资源。

Windows 主机与 Ubuntu VM 的 IP 应分别记录。用户访问 ERP 时使用 Ubuntu VM 的地址，不是 Windows 主机地址。

### 6.2 Ubuntu：安装 Docker 和导入镜像

将 U 盘内容复制到 Ubuntu VM，例如 `/opt/ajierp-offline`。安装离线 Docker 包：

```bash
cd /opt/ajierp-offline/docker-debs
sudo dpkg -i ./*.deb dependencies/*.deb
sudo systemctl enable --now docker
docker version
docker compose version
```

导入镜像：

```bash
docker load -i /opt/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar
docker image ls
```

### 6.3 生成局域网部署编排

初次上线建议采用局域网直连 `8080`，避免客户 DNS、端口策略和公网证书影响部署：

```bash
sudo mkdir -p /opt/ajierp
sudo cp -a /opt/ajierp-offline/project/frappe_docker/. /opt/ajierp/
sudo cp /opt/ajierp-offline/config/.env /opt/ajierp/.env
sudo mkdir -p /opt/ajierp/gitops

cd /opt/ajierp
sudo sh -c 'docker compose --env-file .env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml \
  config > gitops/docker-compose.yml'

sudo docker compose -p ajierp -f gitops/docker-compose.yml up -d
sudo docker compose -p ajierp -f gitops/docker-compose.yml ps
```

局域网访问地址为：

```text
http://<Ubuntu_VM_IP>:8080
```

### 6.4 恢复已有站点

启动后，先确认 `configurator` 已成功结束、MariaDB 正常：

```bash
sudo docker compose -p ajierp -f gitops/docker-compose.yml ps
sudo docker compose -p ajierp -f gitops/docker-compose.yml logs configurator
```

恢复操作需要使用旧站点名、SQL 文件和文件备份。恢复前先在测试环境演练一次；不同 Frappe/ERPNext 大版本的恢复和迁移不能跳过版本兼容验证。

先使用相同站点名创建空站点，再将三个备份文件复制进后台容器并恢复：

```bash
# 仅用于准备站点结构；完成后数据会被 SQL 备份覆盖。
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend \
  bench new-site <旧站点名> \
  --mariadb-user-host-login-scope='%' \
  --db-root-password '<数据库密码>' \
  --admin-password '<临时管理员密码>' \
  --install-app erpnext

sudo docker compose -p ajierp -f gitops/docker-compose.yml cp \
  /opt/ajierp-offline/backup/<旧站点名>/. backend:/tmp/restore

sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend \
  bench --site <旧站点名> restore /tmp/restore/<数据库备份>.sql.gz \
  --with-public-files /tmp/restore/<公有文件备份>.tar \
  --with-private-files /tmp/restore/<私有文件备份>.tar
```

将尖括号中的文件名替换为实际文件名。文件后缀可能是 `.tar`、`.tar.gz` 或其他备份实际格式，以旧服务器 `private/backups` 中生成的文件为准。

恢复完成后执行：

```bash
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend \
  bench --site <站点名> migrate

sudo docker compose -p ajierp -f gitops/docker-compose.yml restart
```

### 6.5 新建空站点（仅无历史数据时）

```bash
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend \
  bench new-site <站点名> \
  --mariadb-user-host-login-scope='%' \
  --db-root-password '<数据库密码>' \
  --admin-password '<ERP管理员密码>' \
  --install-app erpnext
```

## 7. 验收清单

- Docker 容器均为运行状态；`configurator` 已成功退出。
- 管理员能登录并修改初始密码。
- 任意电脑能通过客户局域网访问 Ubuntu VM 的 `8080` 端口。
- 历史单据、主数据、附件和图片可正常打开。
- Excel 导入、库存/财务关键报表、打印格式各验证一次。
- 后台任务和计划任务正常运行。
- SMTP 邮件、打印机、扫码设备按客户实际需求验证。
- 重启 Ubuntu VM 后，容器自动启动且站点仍可访问。
- 完成一次完整备份，并在第二个存储位置保存。

## 8. 上线后的安全与运维

- Windows 和 Ubuntu 均设置自动安全更新，但 ERPNext 版本升级应先在测试环境验证。
- 防火墙仅开放必要端口：局域网方案开放 `8080`；公网 HTTPS 开放 `80/443`。不要向外暴露 MariaDB `3306` 或 Redis。
- 每日至少一次 `bench --site all backup --with-files`，备份同步到 NAS、另一台服务器或对象存储。
- 不要执行 `docker compose down -v`；`-v` 会删除数据库与站点 Docker Volume。
- 定期检查磁盘：数据库、附件、镜像和备份会持续增长。至少保留 150 GB 可用空间。
- 每季度做一次异机恢复演练。存在备份文件不代表备份可恢复。
- Docker 用户组等同于高权限访问；仅给受授权运维人员 SSH 和 Docker 权限。

## 9. 故障排查常用命令

```bash
cd /opt/ajierp
sudo docker compose -p ajierp -f gitops/docker-compose.yml ps
sudo docker compose -p ajierp -f gitops/docker-compose.yml logs --tail=200 backend
sudo docker compose -p ajierp -f gitops/docker-compose.yml logs --tail=200 frontend
sudo docker compose -p ajierp -f gitops/docker-compose.yml logs --tail=200 db
docker stats
df -h
```
