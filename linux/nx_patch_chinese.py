"""
NoMachine 二进制补丁工具 (Linux 版) - 将 Portuguese 替换为 Chinese

原理:
  NoMachine 的支持语言列表是硬编码在 nxplayer.bin 和 nxrunner.bin 中的。
  本工具将 Portuguese (葡萄牙语) 替换为 Chinese (中文)，使 NoMachine 能够
  加载 zh_CN 语言文件。

使用:
  sudo python3 nx_patch_chinese.py             # 显示帮助
  sudo python3 nx_patch_chinese.py --install   # 应用补丁（停止服务→修补→安装翻译→启动服务）
  sudo python3 nx_patch_chinese.py --restore   # 恢复原始文件
  sudo python3 nx_patch_chinese.py --stop      # 停止 NoMachine 服务和 Player（并显示配置文件路径）
  sudo python3 nx_patch_chinese.py --start     # 启动 NoMachine 服务和 Player

前提:
  - 需要 root 权限修改 /usr/NX 下的文件
"""

import os
import sys
import shutil
import subprocess


def detect_nx_dir():
    """自动检测 NoMachine 安装路径"""
    candidates = ['/usr/NX', '/opt/NoMachine']
    for d in candidates:
        if os.path.isdir(d) and os.path.exists(os.path.join(d, 'bin')):
            return d
    return None


NX_DIR = detect_nx_dir()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_bin_dir():
    if NX_DIR is None:
        print('错误: 未找到 NoMachine 安装目录 (/usr/NX 或 /opt/NoMachine)')
        sys.exit(1)
    return os.path.join(NX_DIR, 'bin')


def get_images_dir():
    return os.path.join(NX_DIR, 'share', 'images', 'player')


def get_locale_dir():
    return os.path.join(NX_DIR, 'share', 'locale')


def nx_service(action):
    """停止或启动 NoMachine 服务"""
    nxserver = os.path.join(NX_DIR, 'bin', 'nxserver') if NX_DIR else None
    if not nxserver or not os.path.exists(nxserver):
        for path in ['/etc/NX/nxserver', '/usr/NX/bin/nxserver']:
            if os.path.exists(path):
                nxserver = path
                break
    if not nxserver:
        print(f'  警告: 未找到 nxserver 命令，请手动{action}服务')
        return False

    label = '停止' if action == 'stop' else '启动'
    cmd = '--shutdown' if action == 'stop' else '--startup'
    print(f'  正在{label} NoMachine 服务...')
    result = subprocess.run([nxserver, cmd], capture_output=True, text=True)
    if result.returncode == 0:
        print(f'  服务已{label}')
    else:
        output = result.stdout + result.stderr
        print(f'  {output.strip()}')
    return result.returncode == 0


def patch_binary(filepath, replacements):
    """在二进制文件中执行字符串替换"""
    backup = filepath + '.bak'
    if not os.path.exists(backup):
        shutil.copy2(filepath, backup)
        print(f'  已备份: {backup}')

    with open(filepath, 'rb') as f:
        data = bytearray(f.read())

    total = 0
    for old_bytes, new_bytes in replacements:
        if len(new_bytes) > len(old_bytes):
            print(f'  错误: 新字符串比原字符串长')
            return False

        padded = new_bytes + b'\x00' * (len(old_bytes) - len(new_bytes))

        count = 0
        start = 0
        while True:
            idx = data.find(old_bytes, start)
            if idx == -1:
                break
            data[idx:idx + len(old_bytes)] = padded
            count += 1
            start = idx + len(old_bytes)

        old_str = old_bytes.decode('utf-8', errors='replace')
        new_str = new_bytes.decode('utf-8', errors='replace')
        total += count
        status = f'{count} 处' if count else '未找到'
        print(f'  "{old_str}" -> "{new_str}": {status}')

    if total > 0:
        with open(filepath, 'wb') as f:
            f.write(bytes(data))
    print(f'  共 {total} 处替换')
    return True


def get_server_cfg_path():
    """获取 server.cfg 路径"""
    if NX_DIR is None:
        return None
    return os.path.join(NX_DIR, 'etc', 'server.cfg')


def apply_patches():
    bin_dir = get_bin_dir()
    locale_dir = get_locale_dir()
    img_dir = get_images_dir()

    print('=== 停止 NoMachine 服务 ===')
    nx_service('stop')

    print('=== 修补 nxplayer.bin ===')
    player = [
        (b'nxplayer_pt_PT', b'nxplayer_zh_CN'),
        (b'Portuguese', b'Chinese'),
        (b'Portugu\xc3\xaas', b'\xe4\xb8\xad\xe6\x96\x87'),
        (b'pt-PT', b'zh-CN'),
        (b'\x00pt\x00Spanish', b'\x00zh\x00Spanish'),
        (b'flag-pt.png', b'flag-cn.png'),
    ]
    patch_binary(os.path.join(bin_dir, 'nxplayer.bin'), player)

    print()
    print('=== 修补 nxrunner.bin ===')
    runner = [
        (b'nxrunner_pt_PT', b'nxrunner_zh_CN'),
        (b'Portuguese', b'Chinese'),
        (b'pt-PT', b'zh-CN'),
        (b'\x00pt\x00Spanish', b'\x00zh\x00Spanish'),
    ]
    patch_binary(os.path.join(bin_dir, 'nxrunner.bin'), runner)

    print()
    print('=== 安装 .qm 翻译文件 ===')
    for component in ['nxplayer', 'nxrunner']:
        qm_src = os.path.join(SCRIPT_DIR, f'{component}_zh_CN.qm')
        qm_dst = os.path.join(locale_dir, f'{component}_zh_CN.qm')
        if os.path.exists(qm_src):
            shutil.copy2(qm_src, qm_dst)
            print(f'  已安装: {qm_dst}')
        else:
            print(f'  未找到: {qm_src}')

    print()
    print('=== 创建国旗图标 ===')
    flag_pt = os.path.join(img_dir, 'flag-pt.png')
    flag_cn = os.path.join(img_dir, 'flag-cn.png')
    if not os.path.exists(flag_cn) and os.path.exists(flag_pt):
        shutil.copy2(flag_pt, flag_cn)
        print(f'  已创建: {flag_cn}')
    elif os.path.exists(flag_cn):
        print(f'  已存在: {flag_cn}')

    print()
    print('=== 更新 player.cfg ===')
    sudo_user = os.environ.get('SUDO_USER', '')
    if sudo_user:
        home_dir = os.path.expanduser(f'~{sudo_user}')
    else:
        home_dir = os.path.expanduser('~')
    cfg_path = os.path.join(home_dir, '.nx', 'config', 'player.cfg')
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = f.read()
        if 'Language" value="English' in cfg:
            cfg = cfg.replace('Language" value="English', 'Language" value="Chinese')
            with open(cfg_path, 'w', encoding='utf-8') as f:
                f.write(cfg)
            print(f'  已设置: Language = Chinese')
        elif 'Language" value="Chinese' in cfg:
            print(f'  已是 Chinese')
    else:
        print(f'  未找到: {cfg_path}')

    print()
    print('=== 启动 NoMachine 服务 ===')
    nx_service('start')


def restore_patches():
    bin_dir = get_bin_dir()
    locale_dir = get_locale_dir()
    img_dir = get_images_dir()

    sudo_user = os.environ.get('SUDO_USER', '')
    if sudo_user:
        home_dir = os.path.expanduser(f'~{sudo_user}')
    else:
        home_dir = os.path.expanduser('~')

    print('=== 停止 NoMachine 服务 ===')
    nx_service('stop')

    print()
    print('=== 恢复原始文件 ===')
    for name in ['nxplayer.bin', 'nxrunner.bin']:
        backup = os.path.join(bin_dir, name + '.bak')
        target = os.path.join(bin_dir, name)
        if os.path.exists(backup):
            shutil.copy2(backup, target)
            os.remove(backup)
            print(f'  已恢复: {name}')
        else:
            print(f'  无备份: {name}')

    for component in ['nxplayer', 'nxrunner']:
        qm_file = os.path.join(locale_dir, f'{component}_zh_CN.qm')
        if os.path.exists(qm_file):
            os.remove(qm_file)
            print(f'  已删除: {qm_file}')

    flag_cn = os.path.join(img_dir, 'flag-cn.png')
    if os.path.exists(flag_cn):
        os.remove(flag_cn)
        print(f'  已删除: {flag_cn}')

    cfg_path = os.path.join(home_dir, '.nx', 'config', 'player.cfg')
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = f.read()
        cfg = cfg.replace('Language" value="Chinese', 'Language" value="English')
        with open(cfg_path, 'w', encoding='utf-8') as f:
            f.write(cfg)
        print(f'  已恢复: Language = English')

    print()
    print('=== 启动 NoMachine 服务 ===')
    nx_service('start')


if __name__ == '__main__':
    print('NoMachine 中文补丁工具 v1.5 (Linux)')
    print(f'检测到安装路径: {NX_DIR or "未找到"}')

    has_arg = len(sys.argv) > 1
    is_install = has_arg and sys.argv[1] == '--install'
    is_restore = has_arg and sys.argv[1] == '--restore'
    is_stop = has_arg and sys.argv[1] == '--stop'
    is_start = has_arg and sys.argv[1] == '--start'

    # 无参数 → 显示帮助
    if not has_arg:
        print()
        print(__doc__)
        sys.exit(0)

    print()

    if is_stop:
        subprocess.run(['pkill', 'nxplayer'], capture_output=True)
        nx_service('stop')
        print()
        print('NoMachine 服务和 Player 已停止。')
        print()
        print('配置文件路径（可手动编辑）:')
        if NX_DIR:
            print(f'  server.cfg : {os.path.join(NX_DIR, "etc", "server.cfg")}')
            print(f'  node.cfg   : {os.path.join(NX_DIR, "etc", "node.cfg")}')
        sudo_user = os.environ.get('SUDO_USER', '')
        home_dir = os.path.expanduser(f'~{sudo_user}') if sudo_user else os.path.expanduser('~')
        print(f'  player.cfg : {os.path.join(home_dir, ".nx", "config", "player.cfg")}')
        sys.exit(0)

    if is_start:
        nx_service('start')
        print()
        print('NoMachine 服务已启动。')
        sys.exit(0)

    if is_restore:
        restore_patches()
    elif is_install:
        apply_patches()
        print()
        print('补丁完成！')
