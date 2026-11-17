# ERPNext Windows Server 离线部署（小白版）

适用：客户提供 Windows Server 2019/2022，使用 U 盘部署本项目。假设你有 Windows 管理员账号和客户网络信息。

## 核心结论

不能直接用 Mirantis Container Runtime（MCR）运行这个项目。MCR 是 Windows Server 的 Windows 容器运行时；本项目的 ERPNext、MariaDB、Redis 都是 Linux 容器。

正确架构：

```text
Windows Server
  -> Hyper-V
    -> Ubuntu Server 24.04 虚拟机
      -> Docker Engine + Docker Compose
        -> ERPNext / MariaDB / Redis
```

客户浏览器访问 Ubuntu 虚拟机的 IP，例如 `http://192.168.1.50:8080`，不是 Windows Server 的 IP。MCR 只有在客户另有 Windows 容器需求时才安装，与 ERPNext 无关。

## 一、出发前准备

### 1. 硬件和账号

- 至少 64 GB 的 U 盘，格式为 **exFAT**，不要用 FAT32。
- Windows Server 管理员账号和客户 IT 联系人。
- Windows 主机与 Ubuntu 虚拟机的固定 IP、掩码、网关、DNS。
- 有线业务网络。访客 WiFi 可能禁止设备互访。
- BIOS 中已开启 `SVM` 或 `AMD-V`，否则 Hyper-V 不能运行。

为 Ubuntu VM 分配：3 个 vCPU、12 GB 固定内存、350 GB 动态 VHDX、外部虚拟交换机。Windows 主机保留约 4 GB 内存。

### 2. U 盘文件清单

```text
ajierp-offline/
  iso/ubuntu-24.04.*-live-server-amd64.iso
  project/frappe_docker/             # 当前项目完整目录
  docker-images/ajierp-images-v16.32.0.tar
  docker-debs/                       # Ubuntu 24.04 amd64 Docker .deb 包
  config/.env                        # 生产配置和数据库密码
  config/deployment-notes.txt        # 网络、域名、账号记录
  backup/<旧站点名>/                 # SQL 和附件备份；新系统可为空
  custom-apps/                       # 有自定义 App 时必须准备
```

`docker-debs/` 应包含：`containerd.io`、`docker-ce-cli`、`docker-ce`、`docker-buildx-plugin`、`docker-compose-plugin` 的 `.deb` 文件及其依赖。最稳妥的办法是先在一台断网的 Ubuntu 24.04 测试 VM 上安装一遍，直到 `docker compose version` 成功。

### 3. 导出离线 Docker 镜像

在当前可联网电脑执行：

```bash
cd /home/cst/frappe_docker
docker pull frappe/erpnext:v16.32.0
docker pull mariadb:11.8
docker pull redis:8.6-alpine
docker save -o /path/to/U盘/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar frappe/erpnext:v16.32.0 mariadb:11.8 redis:8.6-alpine
ls -lh /path/to/U盘/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar
```

首次上线使用局域网 `8080`，不需要 Traefik。未来需要公网 HTTPS 时再另行增加 `traefik:v3.6`。

### 4. 创建生产配置

```bash
cd /home/cst/frappe_docker
cp example.env /path/to/U盘/ajierp-offline/config/.env
```

编辑 U 盘中的 `.env`：

```env
ERPNEXT_VERSION=v16.32.0
DB_PASSWORD=替换为至少20位的随机高强度密码
PULL_POLICY=never
FRAPPE_SITE_NAME_HEADER=erp.company.local
GUNICORN_THREADS=4
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120
```

不可保留示例密码 `123`。`PULL_POLICY=never` 保证现场不会尝试从互联网拉镜像。本文后续创建的站点名为 `erp.company.local`，所以这里保持相同；这样用户使用 IP 地址访问时，Frappe 仍能找到正确站点。密码不能提交到 Git 或写入普通 Excel。

### 5. 如果迁移旧系统，导出数据

旧 ERP 服务器执行：

```bash
docker compose -p <旧项目名> exec backend bench --site <旧站点名> backup --with-files
docker compose -p <旧项目名> exec backend bench --site <旧站点名> version
docker compose -p <旧项目名> exec backend bench --site <旧站点名> list-apps
```

将 SQL 数据库备份、`public-files` 和 `private-files` 复制进 `backup/<旧站点名>/`，并保存 `version` 与 `list-apps` 输出。如果有 `frappe`、`erpnext` 之外的 App，必须同时准备自定义 App 源码和构建好的 Linux 镜像，否则恢复后会报错。

### 6. 客户现场前确认

在 `deployment-notes.txt` 记录：服务器 Windows 版本和账号；BIOS 虚拟化状态；固定 IP；内部 DNS 名称；客户 WiFi 才能访问的资料地址和账号；SMTP；打印机；扫码设备；需要导入的 Excel 和附件。

## 二、Windows Server 操作

### 1. 确认虚拟化并启用 Hyper-V

登录 Windows Server，按 `Ctrl + Shift + Esc`，在“性能 -> CPU”确认“虚拟化：已启用”。然后以管理员身份打开 PowerShell：

```powershell
Install-WindowsFeature -Name Hyper-V -IncludeManagementTools -Restart
```

服务器会重启。重启后打开“Hyper-V 管理器”。如果任务管理器显示虚拟化未启用，请让客户硬件管理员在 BIOS 中开启 SVM/AMD-V，不要随意修改其他 BIOS 设置。

验证状态：

```powershell
Get-WindowsFeature -Name Hyper-V
Get-ComputerInfo -Property HyperVisorPresent
```

`Install State` 应为 `Installed`，`HyperVisorPresent` 应为 `True`。

### 2. 创建外部网络交换机

在 Hyper-V 管理器右侧进入“虚拟交换机管理器”：

1. 选择“新建虚拟网络交换机 -> 外部 -> 创建虚拟交换机”。
2. 名称填写 `BusinessLAN`。
3. 选择接入客户业务网络的实际物理网卡。
4. 勾选“允许管理操作系统共享此网络适配器”。
5. 点击“应用”。网络短暂断开属正常情况。

也可用管理员 PowerShell 创建（先用 `Get-NetAdapter` 查看真实网卡名）：

```powershell
Get-NetAdapter
New-VMSwitch -Name "BusinessLAN" -NetAdapterName "以太网" -AllowManagementOS $true
Get-VMSwitch -Name "BusinessLAN"
```

将 `以太网` 换成实际网卡名；如果已在界面创建交换机，不要重复执行 `New-VMSwitch`。

### 3. 创建 Ubuntu 虚拟机

在 Hyper-V 管理器选择“新建 -> 虚拟机”：

1. 名称填 `ajiERP-Ubuntu`。
2. 选择“第 2 代”。
3. 内存设置为 `12288 MB`，取消动态内存。
4. 网络选择 `BusinessLAN`。
5. 新建 `350 GB` 动态扩展的虚拟硬盘。
6. 安装介质选择 U 盘中的 Ubuntu 24.04 ISO。
7. 完成后点击“连接 -> 启动”。

Ubuntu 使用第 2 代虚拟机时，在管理员 PowerShell 设置适用的 Secure Boot 模板：

```powershell
Set-VMFirmware -VMName "ajiERP-Ubuntu" -EnableSecureBoot On -SecureBootTemplate MicrosoftUEFICertificateAuthority
```

若仍无法从 ISO 启动，可临时关闭该 VM 的 Secure Boot：

```powershell
Set-VMFirmware -VMName "ajiERP-Ubuntu" -EnableSecureBoot Off
```

检查虚拟机设置：

```powershell
Get-VM -Name "ajiERP-Ubuntu"
Get-VMProcessor -VMName "ajiERP-Ubuntu"
Get-VMMemory -VMName "ajiERP-Ubuntu"
```

必要时调整：

```powershell
Set-VMProcessor -VMName "ajiERP-Ubuntu" -Count 3
Set-VMMemory -VMName "ajiERP-Ubuntu" -StartupBytes 12GB -DynamicMemoryEnabled $false
```

## 三、Ubuntu 操作

### 4. 安装 Ubuntu Server

安装向导中：语言和键盘可保持默认；磁盘选择 `Use an entire disk`（只影响 VM 虚拟硬盘）；创建用户名 `erpadmin`；在 `SSH Setup` 页面务必勾选 **Install OpenSSH server**；不安装额外 Snap。安装完成后重启，并在 Hyper-V DVD 设置里移除 ISO。

### 5. 设置 Ubuntu 固定 IP

查看网卡和 Netplan 文件：

```bash
ip a
sudo ls /etc/netplan
sudo nano /etc/netplan/50-cloud-init.yaml
```

以下为示例，网卡名、IP、网关和 DNS 以客户 IT 给出的信息为准：

```yaml
network:
  version: 2
  ethernets:
    ens160:
      dhcp4: false
      addresses: [192.168.1.50/24]
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses: [192.168.1.1, 8.8.8.8]
```

在 `nano` 中按 `Ctrl+O`、回车保存，再按 `Ctrl+X` 退出。执行：

```bash
sudo netplan try
ip a
ping -c 3 <客户网关IP>
```

### 6. 将 U 盘文件传入 Ubuntu

U 盘插在 Windows Server。以管理员 PowerShell 执行，假设 U 盘为 `E:`、Ubuntu IP 为 `192.168.1.50`：

```powershell
scp -r E:\ajierp-offline erpadmin@192.168.1.50:/home/erpadmin/
```

首次连接输入 `yes`，然后输入 Ubuntu 密码。镜像文件很大，等待传输结束，不要拔 U 盘。若 Windows 没有 `scp`，安装 OpenSSH Client 可选功能，或用事先准备好的 WinSCP 上传至 `/home/erpadmin/`。

检查文件：

```bash
ls -lh /home/erpadmin/ajierp-offline/docker-images/
```

可选但推荐：在 Windows 和 Ubuntu 两边计算 SHA256，确保镜像没有损坏：

```powershell
Get-FileHash E:\ajierp-offline\docker-images\ajierp-images-v16.32.0.tar -Algorithm SHA256
```

```bash
sha256sum /home/erpadmin/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar
```

两边的哈希值必须完全相同。

## 四、安装 Docker 并启动 ERPNext

### 7. 安装 Docker

```bash
cd /home/erpadmin/ajierp-offline/docker-debs
sudo dpkg -i ./*.deb dependencies/*.deb
sudo systemctl enable --now docker
sudo usermod -aG docker erpadmin
exit
```

重新登录 Ubuntu，再执行：

```bash
docker version
docker compose version
docker load -i /home/erpadmin/ajierp-offline/docker-images/ajierp-images-v16.32.0.tar
docker image ls
```

应看到 `frappe/erpnext:v16.32.0`、`mariadb:11.8`、`redis:8.6-alpine`。若 `dpkg` 报缺少依赖，不能忽略，先补全 U 盘中的 `.deb` 包。

### 8. 生成配置并启动

```bash
sudo mkdir -p /opt/ajierp/gitops
sudo cp -a /home/erpadmin/ajierp-offline/project/frappe_docker/. /opt/ajierp/
sudo cp /home/erpadmin/ajierp-offline/config/.env /opt/ajierp/.env
cd /opt/ajierp
sudo sh -c 'docker compose --env-file .env -f compose.yaml -f overrides/compose.mariadb.yaml -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml config > gitops/docker-compose.yml'
sudo docker compose -p ajierp -f gitops/docker-compose.yml up -d
sudo docker compose -p ajierp -f gitops/docker-compose.yml ps
sudo docker compose -p ajierp -f gitops/docker-compose.yml logs configurator
```

第一次启动需要数分钟。成功标准：`configurator` 成功退出，`backend`、`frontend`、`db`、Redis、queue、scheduler 等服务为 `Up`。

如果提示 8080 端口被占用：

```bash
sudo ss -lntp | grep ':8080'
```

停止占用该端口的其他服务，或按客户 IT 批准的端口修改配置后重新生成 Compose 文件。

## 五、恢复旧系统或创建新系统

### 情况 A：恢复旧系统

先创建一个和旧系统**完全同名**的空站点，例如 `erp.company.local`：

```bash
cd /opt/ajierp
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend bench new-site erp.company.local --mariadb-user-host-login-scope='%' --db-root-password '<.env中的DB_PASSWORD>' --admin-password '<临时管理员密码>' --install-app erpnext
sudo docker compose -p ajierp -f gitops/docker-compose.yml cp /home/erpadmin/ajierp-offline/backup/erp.company.local/. backend:/tmp/restore
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend ls -lh /tmp/restore
```

根据上条命令显示的实际文件名恢复：

```bash
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend bench --site erp.company.local restore /tmp/restore/<数据库备份>.sql.gz --with-public-files /tmp/restore/<公有附件备份>.tar --with-private-files /tmp/restore/<私有附件备份>.tar
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend bench --site erp.company.local migrate
sudo docker compose -p ajierp -f gitops/docker-compose.yml restart
```

附件文件后缀可能是 `.tar.gz`，按真实文件名写。恢复成功后使用旧管理员账号登录。

`restore` 如果询问 MariaDB root 密码，输入 `.env` 中的 `DB_PASSWORD`；终端输入密码时不会显示字符，这是正常情况。

### 情况 B：全新系统

```bash
cd /opt/ajierp
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend bench new-site erp.company.local --mariadb-user-host-login-scope='%' --db-root-password '<.env中的DB_PASSWORD>' --admin-password '<ERP管理员密码>' --install-app erpnext
```

## 六、验收、备份与禁忌

客户电脑浏览器访问 `http://<Ubuntu_IP>:8080`。依次验证：登录、历史数据、附件、Excel 导入、常用报表、打印、邮件与扫码设备。然后重启 Ubuntu VM，确认容器自动启动。

设置防火墙：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8080/tcp
sudo ufw enable
sudo ufw status
```

每天至少做一次完整备份，并复制到 Ubuntu VM 以外的 NAS 或另一设备：

```bash
cd /opt/ajierp
sudo docker compose -p ajierp -f gitops/docker-compose.yml exec backend bench --site all backup --with-files
```

**禁止执行 `docker compose down -v`。** `-v` 会删除站点和数据库 Volume。日常停止服务只使用：

```bash
sudo docker compose -p ajierp -f /opt/ajierp/gitops/docker-compose.yml down
```

排错常用命令：

```bash
cd /opt/ajierp
sudo docker compose -p ajierp -f gitops/docker-compose.yml ps
sudo docker compose -p ajierp -f gitops/docker-compose.yml logs --tail=200 backend
sudo docker compose -p ajierp -f gitops/docker-compose.yml logs --tail=200 db
docker stats
df -h
```

完成标准：ERP 可从客户局域网访问，数据和附件正确，管理员密码已交付，验证过重启，并且完整备份已保存到第二个物理存储位置。
