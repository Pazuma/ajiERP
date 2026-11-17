#!/usr/bin/env bash
set -euo pipefail
aki_app=/srv/aki-erp/deploy-20260930/aki-erp-full-20260929-182611/frappe_docker/development/frappe-bench/apps/client_akivision
aki_archive=/home/yuewei/bom_drawing_aki_icons_fix_20261104.tar.gz
aki_container=aki_full_20260930_frappe_1
aki_bench=/workspace/development/frappe-bench
test -d "$aki_app"
test -f "$aki_archive"
sudo -v
# Use the existing BOM integration; do not overwrite unrelated server hooks.
sudo docker exec -i -w "$aki_bench" "$aki_container" env/bin/python <<'PY'
from pathlib import Path
content = Path('apps/client_akivision/client_akivision/hooks.py').read_text()
for required in ('client_akivision.utils.bom.AkivisionBOMMixin', 'client_akivision.utils.bom.ensure_schema', 'public/js/bom.js'):
    if required not in content:
        raise SystemExit('缺少既有 BOM 接入配置，停止部署，请反馈此输出：' + required)
print('既有 BOM 接入配置检查通过')
PY
aki_backup=$(mktemp -d /home/yuewei/bom-drawing-before-XXXXXX)
tar -tzf "$aki_archive" > "$aki_backup/package-files.txt"
while IFS= read -r aki_rel; do
  case "$aki_rel" in
    client_akivision/utils/bom.py|client_akivision/public/js/bom.js|client_akivision/public/js/desktop_icon_logo.js|client_akivision/public/images/aki_sidebar_icon.svg) ;;
    *) echo "非预期补丁文件：$aki_rel"; exit 1 ;;
  esac
  if sudo test -f "$aki_app/$aki_rel"; then
    sudo mkdir -p "$aki_backup/files/$(dirname "$aki_rel")"
    sudo cp -a "$aki_app/$aki_rel" "$aki_backup/files/$aki_rel"
  else
    printf '%s\n' "$aki_rel" >> "$aki_backup/new-files.txt"
  fi
done < "$aki_backup/package-files.txt"
echo "旧文件备份：$aki_backup"
sudo mkdir -p "$aki_backup/files/client_akivision"
sudo cp -a "$aki_app/client_akivision/hooks.py" "$aki_backup/files/client_akivision/hooks.py"
sudo docker exec -w "$aki_bench" "$aki_container" bench --site aki_test.localhost backup
sudo tar -xzf "$aki_archive" -C "$aki_app" --no-same-owner
# Append only the required branding configuration, preserving server hooks.
sudo docker exec -u 0 -i -w "$aki_bench" "$aki_container" env/bin/python <<'PY'
from pathlib import Path
path = Path('apps/client_akivision/client_akivision/hooks.py')
content = path.read_text()
marker = '# AKI BOM drawing and icons deployment 20261104'
if marker not in content:
    content += '''
# AKI BOM drawing and icons deployment 20261104
favicon = "/assets/client_akivision/images/aki_sidebar_icon.svg?v=2026110402"
_aki_icon_scripts = globals().get("app_include_js", [])
_aki_icon_scripts = [_aki_icon_scripts] if isinstance(_aki_icon_scripts, str) else list(_aki_icon_scripts)
app_include_js = [script for script in _aki_icon_scripts if script.split("?")[0] != "/assets/client_akivision/js/desktop_icon_logo.js"] + ["/assets/client_akivision/js/desktop_icon_logo.js?v=2026110402"]
'''
    compile(content, str(path), 'exec')
    path.write_text(content)
print('AKI 图标配置已就绪')
PY
sudo docker exec -w "$aki_bench" "$aki_container" env/bin/python -m py_compile apps/client_akivision/client_akivision/utils/bom.py
sudo docker exec -w "$aki_bench" "$aki_container" node --check apps/client_akivision/client_akivision/public/js/bom.js
sudo docker exec -w "$aki_bench" "$aki_container" bench --site aki_test.localhost execute client_akivision.utils.bom.ensure_schema
sudo docker exec -w "$aki_bench" "$aki_container" bench build --app client_akivision
sudo docker exec -w "$aki_bench" "$aki_container" bench --site aki_test.localhost clear-cache
sudo docker restart "$aki_container"
echo "部署命令执行完成。请稍后检查登录页，并强制刷新浏览器。"
echo "旧文件备份：$aki_backup"
