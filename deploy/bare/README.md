# 常规部署（bare metal / systemd）

不依赖 Docker，直接把后端 + 预构建前端装到系统目录，用 systemd 托管。
适合：已有 Python 3.10+ 的 Linux、群晖/威联通自带系统、想自己控制进程与端口的场景。

## 一、用分发包安装（推荐）

```bash
# 1. 拿到包与校验值
sha256sum -c echoshelf-0.1.0-linux-amd64-bare.tar.gz.sha256

# 2. 解压并安装
tar xzf echoshelf-0.1.0-linux-amd64-bare.tar.gz
cd echoshelf-0.1.0-linux-amd64
sudo ./install.sh --audiobooks /volume1/media/audiobooks
```

安装脚本会做这些事：

```
1. 检查 python3 ≥ 3.10 / ffmpeg（缺失只告警）
2. 复制 app/ 与 web/dist/ 到 /opt/echoshelf
3. 建 venv 并安装 requirements-prod.txt（--offline 时用包内 wheels/）
4. 生成 /etc/echoshelf/echoshelf.env（已存在则不覆盖）
5. 建系统用户 echoshelf，数据目录归它所有
6. alembic upgrade head 初始化/升级数据库
7. 安装 /etc/systemd/system/echoshelf.service 并启动
```

安装完成后：

```bash
systemctl status echoshelf
journalctl -u echoshelf -f
curl -s http://127.0.0.1:8080/api/v1/health
```

然后创建唯一管理员（网页端不提供创建入口）：

```bash
sudo -u echoshelf /opt/echoshelf/bin/echoshelf admin create
sudo -u echoshelf /opt/echoshelf/bin/echoshelf admin reset-password   # 忘记密码
```

再打开 `http://<机器IP>:8080` 登录，到「设置 → 书库」登记媒体目录。

## 二、常见参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prefix DIR` | `/opt/echoshelf` | 程序目录 |
| `--data-dir DIR` | `/var/lib/echoshelf` | 数据库 / 封面 / 转码缓存 / 日志 |
| `--audiobooks DIR` | `/srv/audiobooks` | 媒体库根目录，装完可再改 |
| `--env-dir DIR` | `/etc/echoshelf` | 配置文件目录 |
| `--port PORT` | `8080` | HTTP 端口 |
| `--user NAME` | `echoshelf` | 运行身份 |
| `--no-service` | — | 不装 systemd，仅准备文件与 venv |
| `--no-user` | — | 不建系统用户（当前用户运行） |
| `--offline` | — | 用包内 `wheels/` 离线装依赖 |
| `--skip-migrate` | — | 跳过数据库迁移 |

## 三、没有 systemd 时

安装脚本已经生成了前台启动器：

```bash
/opt/echoshelf/bin/echoshelf          # 读取 /etc/echoshelf/echoshelf.env 后前台运行
```

可以配 `nohup`、`supervisord`、群晖「任务计划」或 OpenWrt 的 procd 来常驻。

## 四、升级

```bash
tar xzf echoshelf-0.2.0-linux-amd64-bare.tar.gz
cd echoshelf-0.2.0-linux-amd64
sudo ./install.sh          # 复用已有配置与数据，代码整体替换
```

`install.sh` 会先复制到 `app.new/` 再整体替换，不会残留旧文件；迁移在启动前执行。

## 五、反向代理（可选）

`deploy/nginx.conf` 是现成模板，要点两条：

- 音频流路径关闭代理缓冲（`proxy_buffering off`），否则拖动进度会卡
- `client_max_body_size` 至少 5m（封面上传）

## 六、卸载

```bash
sudo ./uninstall.sh            # 删程序与配置，保留数据
sudo ./uninstall.sh --purge    # 连数据目录一起删（会二次确认）
```
