"""
NoMachine 二进制补丁工具 (macOS 版) - 将 Portuguese 替换为 Chinese

原理:
  NoMachine 的支持语言列表是硬编码在 nxplayer 和 nxrunner 二进制文件中的。
  本工具将 Portuguese (葡萄牙语) 替换为 Chinese (中文)，使 NoMachine 能够
  加载 zh_CN 语言文件。

使用:
  sudo python3 nx_patch_chinese.py             # 显示帮助
  sudo python3 nx_patch_chinese.py --install   # 应用补丁（停止服务→修补→安装翻译→启动服务→重启Player）
  sudo python3 nx_patch_chinese.py --restore   # 恢复原始文件
  sudo python3 nx_patch_chinese.py --stop      # 停止 NoMachine 服务和 Player（并显示配置文件路径）
  sudo python3 nx_patch_chinese.py --start     # 启动 NoMachine 服务和 Player

前提:
  - 需要管理员权限修改 /Applications/NoMachine.app 下的文件
"""

import os
import sys
import shutil
import subprocess


def detect_nx_dir():
    """自动检测 NoMachine 安装路径"""
    candidates = ['/Applications/NoMachine.app', '/usr/NX', '/opt/NoMachine']
    for d in candidates:
        if not os.path.isdir(d):
            continue
        if d.endswith('.app'):
            locale_path = os.path.join(d, 'Contents', 'Frameworks', 'share', 'locale')
        else:
            locale_path = os.path.join(d, 'share', 'locale')
        if os.path.exists(locale_path):
            return d
    return None


NX_DIR = detect_nx_dir()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_nxplayer_bin():
    if NX_DIR is None:
        print('错误: 未找到 NoMachine 安装目录')
        sys.exit(1)
    if NX_DIR.endswith('.app'):
        return os.path.join(NX_DIR, 'Contents', 'MacOS', 'nxplayer')
    return os.path.join(NX_DIR, 'bin', 'nxplayer.bin')


def get_nxrunner_bin():
    if NX_DIR is None:
        print('错误: 未找到 NoMachine 安装目录')
        sys.exit(1)
    if NX_DIR.endswith('.app'):
        return os.path.join(NX_DIR, 'Contents', 'Frameworks', 'bin', 'nxrunner.app', 'Contents', 'MacOS', 'nxrunner')
    return os.path.join(NX_DIR, 'bin', 'nxrunner.bin')


def get_images_dir():
    if NX_DIR.endswith('.app'):
        return os.path.join(NX_DIR, 'Contents', 'Frameworks', 'share', 'images', 'player')
    return os.path.join(NX_DIR, 'share', 'images', 'player')


def get_locale_dir():
    if NX_DIR.endswith('.app'):
        return os.path.join(NX_DIR, 'Contents', 'Frameworks', 'share', 'locale')
    return os.path.join(NX_DIR, 'share', 'locale')


def get_nxserver_bin():
    if NX_DIR.endswith('.app'):
        return os.path.join(NX_DIR, 'Contents', 'Frameworks', 'bin', 'nxserver')
    return os.path.join(NX_DIR, 'bin', 'nxserver')


def get_home_dir():
    """获取实际用户的 home 目录（sudo 下使用 SUDO_USER）"""
    sudo_user = os.environ.get('SUDO_USER', '')
    if sudo_user:
        return os.path.expanduser(f'~{sudo_user}')
    return os.path.expanduser('~')


def sudo_copy(src, dst):
    """使用 cp 命令复制文件，绕过 macOS SIP 对 Python 的限制"""
    result = subprocess.run(['cp', src, dst], capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  警告: 复制失败: {result.stderr.strip()}')


def nx_service(action):
    """停止或启动 NoMachine 服务"""
    nxserver = get_nxserver_bin()
    if not os.path.exists(nxserver):
        print(f'  警告: 未找到 nxserver，请手动{action}服务')
        return False

    cmd = f'--{"shutdown" if action == "停止" else "startup"}'
    print(f'  正在{action} NoMachine 服务...')
    result = subprocess.run([nxserver, cmd], capture_output=True, text=True)
    if result.returncode == 0:
        print(f'  服务已{action}')
    else:
        output = result.stdout + result.stderr
        print(f'  {output.strip()}')
    return result.returncode == 0


def restart_nxplayer():
    """重启 NoMachine Player 应用"""
    # 先关闭
    subprocess.run(['pkill', '-f', 'NoMachine.app.*Contents/MacOS/nxplayer'],
                   capture_output=True)
    # 以实际用户身份重新打开
    sudo_user = os.environ.get('SUDO_USER', '')
    if sudo_user:
        subprocess.run(['sudo', '-u', sudo_user, 'open', '-a', 'NoMachine'],
                       capture_output=True)
    else:
        subprocess.run(['open', '-a', 'NoMachine'], capture_output=True)
    print('  已重启 NoMachine Player')


def patch_binary(filepath, replacements):
    """在二进制文件中执行字符串替换"""
    if not os.access(filepath, os.W_OK):
        print(f'  错误: 没有写入权限: {filepath}')
        print(f'  请使用 sudo 运行: sudo python3 {os.path.basename(__file__)}')
        return False

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
    if NX_DIR.endswith('.app'):
        return os.path.join(NX_DIR, 'Contents', 'Frameworks', 'etc', 'server.cfg')
    return os.path.join(NX_DIR, 'etc', 'server.cfg')


def apply_patches():
    locale_dir = get_locale_dir()
    img_dir = get_images_dir()

    print('=== 停止 NoMachine 服务 ===')
    nx_service('停止')

    print()
    print('=== 修补 nxplayer 二进制 ===')
    player = [
        (b'nxplayer_pt_PT', b'nxplayer_zh_CN'),
        (b'Portuguese', b'Chinese'),
        (b'Portugu\xc3\xaas', b'\xe4\xb8\xad\xe6\x96\x87'),
        (b'pt-PT', b'zh-CN'),
        (b'\x00pt\x00Spanish', b'\x00zh\x00Spanish'),
        (b'flag-pt.png', b'flag-cn.png'),
    ]
    patch_binary(get_nxplayer_bin(), player)

    print()
    print('=== 修补 nxrunner 二进制 ===')
    runner = [
        (b'nxrunner_pt_PT', b'nxrunner_zh_CN'),
        (b'Portuguese', b'Chinese'),
        (b'pt-PT', b'zh-CN'),
        (b'\x00pt\x00Spanish', b'\x00zh\x00Spanish'),
    ]
    patch_binary(get_nxrunner_bin(), runner)

    print()
    print('=== 安装 .qm 翻译文件 ===')
    for component in ['nxplayer', 'nxrunner']:
        qm_src = os.path.join(SCRIPT_DIR, f'{component}_zh_CN.qm')
        qm_dst = os.path.join(locale_dir, f'{component}_zh_CN.qm')
        if os.path.exists(qm_src):
            sudo_copy(qm_src, qm_dst)
            print(f'  已安装: {qm_dst}')
        else:
            print(f'  未找到: {qm_src}')

    print()
    print('=== 创建国旗图标 ===')
    flag_pt = os.path.join(img_dir, 'flag-pt.png')
    flag_cn = os.path.join(img_dir, 'flag-cn.png')
    if not os.path.exists(flag_cn) and os.path.exists(flag_pt):
        sudo_copy(flag_pt, flag_cn)
        print(f'  已创建: {flag_cn}')
    elif os.path.exists(flag_cn):
        print(f'  已存在: {flag_cn}')

    print()
    print('=== 更新 player.cfg ===')
    home_dir = get_home_dir()
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
    nx_service('启动')

    print()
    print('=== 重启 NoMachine Player ===')
    restart_nxplayer()


def restore_patches():
    """通过反向替换恢复原始文件"""
    locale_dir = get_locale_dir()
    img_dir = get_images_dir()
    home_dir = get_home_dir()

    print('=== 停止 NoMachine 服务 ===')
    nx_service('停止')

    print()
    print('=== 恢复 nxplayer 二进制 ===')
    player = [
        (b'nxplayer_zh_CN', b'nxplayer_pt_PT'),
        (b'Chinese\x00\x00\x00', b'Portuguese'),
        (b'\xe4\xb8\xad\xe6\x96\x87\x00\x00\x00\x00', b'Portugu\xc3\xaas'),
        (b'zh-CN', b'pt-PT'),
        (b'flag-cn.png', b'flag-pt.png'),
    ]
    patch_binary(get_nxplayer_bin(), player)

    print()
    print('=== 恢复 nxrunner 二进制 ===')
    runner = [
        (b'nxrunner_zh_CN', b'nxrunner_pt_PT'),
        (b'Chinese\x00\x00\x00', b'Portuguese'),
        (b'zh-CN', b'pt-PT'),
    ]
    patch_binary(get_nxrunner_bin(), runner)

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
    nx_service('启动')

    print()
    print('=== 重启 NoMachine Player ===')
    restart_nxplayer()


if __name__ == '__main__':
    print('NoMachine 中文补丁工具 v1.5 (macOS)')
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

    if os.geteuid() != 0:
        print('错误: 需要管理员权限修改 /Applications/NoMachine.app')
        print('请使用 sudo 运行:')
        print(f'  sudo python3 {" ".join(sys.argv)}')
        sys.exit(1)

    # macOS SIP 不允许 SSH 会话写入 /Applications 目录
    ssh_env = os.environ.get('SSH_CONNECTION', '') or os.environ.get('SSH_CLIENT', '')
    if ssh_env and NX_DIR and NX_DIR.endswith('.app'):
        print('错误: 检测到 SSH 远程会话，macOS SIP 不允许远程写入 /Applications 目录。')
        print('请在 macOS 宿主机上直接打开终端执行本脚本。')
        sys.exit(1)

    # sudo 可能清除 SSH 环境变量，实际检测 SIP 写入权限
    if NX_DIR and NX_DIR.endswith('.app'):
        test_file = os.path.join(get_locale_dir(), '.sip_test')
        try:
            with open(test_file, 'wb') as f:
                f.write(b'test')
            os.remove(test_file)
        except PermissionError:
            print('错误: macOS SIP 阻止了写入 /Applications 目录。')
            print('请在 macOS 宿主机上直接打开终端（非 SSH）执行本脚本。')
            print('或者: 系统偏好设置 → 安全性与隐私 → 隐私 → 完全磁盘访问权限 → 添加终端应用')
            sys.exit(1)

    if is_stop:
        subprocess.run(['pkill', '-f', 'NoMachine.app.*Contents/MacOS/nxplayer'],
                       capture_output=True)
        nx_service('停止')
        print()
        print('NoMachine 服务和 Player 已停止。')
        print()
        print('配置文件路径（可手动编辑）:')
        if NX_DIR:
            if NX_DIR.endswith('.app'):
                etc_dir = os.path.join(NX_DIR, 'Contents', 'Frameworks', 'etc')
            else:
                etc_dir = os.path.join(NX_DIR, 'etc')
            print(f'  server.cfg : {os.path.join(etc_dir, "server.cfg")}')
            print(f'  node.cfg   : {os.path.join(etc_dir, "node.cfg")}')
        home_dir = os.path.expanduser(f'~{os.environ.get("SUDO_USER", "")}' if os.environ.get('SUDO_USER') else '~')
        print(f'  player.cfg : {os.path.join(home_dir, ".nx", "config", "player.cfg")}')
        sys.exit(0)

    if is_start:
        nx_service('启动')
        restart_nxplayer()
        print()
        print('NoMachine 服务和 Player 已启动。')
        sys.exit(0)

    if is_restore:
        restore_patches()
    elif is_install:
        apply_patches()
        print()
        print('补丁完成！')
