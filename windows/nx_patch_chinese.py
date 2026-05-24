"""
NoMachine 二进制补丁工具 (Windows 版) - 将 Portuguese 替换为 Chinese

原理:
  NoMachine 的支持语言列表是硬编码在 nxplayer.bin 和 nxrunner.bin 中的。
  本工具将 Portuguese (葡萄牙语) 替换为 Chinese (中文)，使 NoMachine 能够
  加载 zh_CN 语言文件。

使用:
  python nx_patch_chinese.py             # 显示帮助
  python nx_patch_chinese.py --install   # 停止服务 → 补丁 → 安装翻译 → 启动服务 → 启动Player
  python nx_patch_chinese.py --restore   # 停止服务 → 恢复原始文件 → 启动服务
  python nx_patch_chinese.py --stop      # 停止 NoMachine 服务和 Player（并显示配置文件路径）
  python nx_patch_chinese.py --start     # 启动 NoMachine 服务和 Player

前提:
  - 需要管理员权限
"""

import os
import sys
import shutil
import subprocess
import time


def detect_nx_dir():
    """自动检测 NoMachine 安装路径"""
    candidates = [
        r'C:\Program Files\NoMachine',
        r'C:\Program Files (x86)\NoMachine',
    ]
    # 也尝试从注册表或环境变量获取
    for env_var in ['NX_HOME', 'NOMACHINE_HOME']:
        val = os.environ.get(env_var, '')
        if val and os.path.isdir(val):
            candidates.insert(0, val)

    for d in candidates:
        if os.path.isdir(d) and os.path.exists(os.path.join(d, 'bin')):
            return d
    return None


NX_DIR = detect_nx_dir()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_bin_dir():
    if NX_DIR is None:
        print('错误: 未找到 NoMachine 安装目录')
        print('请确认 NoMachine 已安装到 C:\\Program Files\\NoMachine')
        print('或设置 NX_HOME 环境变量指向安装目录')
        sys.exit(1)
    return os.path.join(NX_DIR, 'bin')


def get_images_dir():
    return os.path.join(NX_DIR, 'share', 'images', 'player')


def get_locale_dir():
    return os.path.join(NX_DIR, 'share', 'locale')


def get_home_dir():
    """获取用户 home 目录"""
    return os.path.expanduser('~')


def run_cmd(cmd, check=False):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if check and result.returncode != 0:
            return False
        return result.returncode == 0
    except Exception:
        return False


def stop_nomachine():
    print('=== 停止 NoMachine 服务 ===')

    # Windows: 先杀进程再停服务
    for proc in ['nxplayer.bin', 'nxrunner.bin', 'nxplayer.exe']:
        run_cmd(['taskkill', '/F', '/IM', proc])
    run_cmd(['net', 'stop', 'nxs']) or run_cmd(['sc', 'stop', 'nxs'])

    # 等待进程退出
    for _ in range(10):
        time.sleep(1)
        r = subprocess.run(['tasklist'], capture_output=True, text=True)
        if 'nxplayer' not in r.stdout.lower() and 'nxrunner' not in r.stdout.lower():
            break

    print('  NoMachine 已停止')


def start_nomachine():
    print()
    print('=== 启动 NoMachine 服务 ===')

    run_cmd(['net', 'start', 'nxs']) or run_cmd(['sc', 'start', 'nxs'])

    print('  NoMachine 服务已启动')


def start_player():
    print()
    print('=== 启动 NoMachine Player ===')

    bin_dir = get_bin_dir()
    player = os.path.join(bin_dir, 'nxplayer.exe')
    subprocess.Popen([player], creationflags=0x00000008)  # DETACHED_PROCESS

    print('  NoMachine Player 已启动')


def patch_binary(filepath, replacements):
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
    return total > 0


def get_server_cfg_path():
    """获取 server.cfg 路径"""
    if NX_DIR is None:
        return None
    return os.path.join(NX_DIR, 'etc', 'server.cfg')


def apply_patches():
    bin_dir = get_bin_dir()
    locale_dir = get_locale_dir()
    img_dir = get_images_dir()
    home_dir = get_home_dir()
    success = True

    print('=== 修补 nxplayer.bin ===')
    player = [
        (b'nxplayer_pt_PT', b'nxplayer_zh_CN'),
        (b'Portuguese', b'Chinese'),
        (b'Portugu\xc3\xaas', b'\xe4\xb8\xad\xe6\x96\x87'),
        (b'pt-PT', b'zh-CN'),
        (b'\x00pt\x00Spanish', b'\x00zh\x00Spanish'),
        (b'flag-pt.png', b'flag-cn.png'),
    ]
    if not patch_binary(os.path.join(bin_dir, 'nxplayer.bin'), player):
        success = False

    print()
    print('=== 修补 nxrunner.bin ===')
    runner = [
        (b'nxrunner_pt_PT', b'nxrunner_zh_CN'),
        (b'Portuguese', b'Chinese'),
        (b'pt-PT', b'zh-CN'),
        (b'\x00pt\x00Spanish', b'\x00zh\x00Spanish'),
    ]
    if not patch_binary(os.path.join(bin_dir, 'nxrunner.bin'), runner):
        success = False

    print()
    print('=== 安装 .qm 翻译文件 ===')
    for component in ['nxplayer', 'nxrunner']:
        qm_src = os.path.join(SCRIPT_DIR, f'{component}_zh_CN.qm')
        qm_dst = os.path.join(locale_dir, f'{component}_zh_CN.qm')
        if os.path.exists(qm_src):
            shutil.copy2(qm_src, qm_dst)
            print(f'  已安装: {qm_dst}')
        else:
            print(f'  未找到: {qm_src} (请先运行 nx_translate.py compile)')

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

    return success


def restore_patches():
    bin_dir = get_bin_dir()
    locale_dir = get_locale_dir()
    img_dir = get_images_dir()
    home_dir = get_home_dir()

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

    # 删除安装的中文 .qm 文件
    for component in ['nxplayer', 'nxrunner']:
        qm_file = os.path.join(locale_dir, f'{component}_zh_CN.qm')
        if os.path.exists(qm_file):
            os.remove(qm_file)
            print(f'  已删除: {qm_file}')

    # 删除国旗图标
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


if __name__ == '__main__':
    print('NoMachine 中文补丁工具 v1.5 (Windows)')
    print(f'检测到安装路径: {NX_DIR or "未找到"}')

    is_install = '--install' in sys.argv
    is_restore = '--restore' in sys.argv
    is_stop = '--stop' in sys.argv
    is_start = '--start' in sys.argv

    # 无参数 → 显示帮助
    if not (is_install or is_restore or is_stop or is_start):
        print()
        print(__doc__)
        sys.exit(0)

    print()

    if is_stop:
        stop_nomachine()
        print()
        print('NoMachine 服务和 Player 已停止。')
        print()
        print('配置文件路径（可手动编辑）:')
        if NX_DIR:
            print(f'  server.cfg : {os.path.join(NX_DIR, "etc", "server.cfg")}')
            print(f'  node.cfg   : {os.path.join(NX_DIR, "etc", "node.cfg")}')
        home_dir = os.path.expanduser('~')
        print(f'  player.cfg : {os.path.join(home_dir, ".nx", "config", "player.cfg")}')
        sys.exit(0)

    if is_start:
        start_nomachine()
        start_player()
        print()
        print('NoMachine 服务和 Player 已启动。')
        sys.exit(0)

    stop_nomachine()

    try:
        if is_restore:
            restore_patches()
        elif is_install:
            ok = apply_patches()
            if not ok:
                print()
                print('补丁可能未完全成功，请检查上方输出。')
    except Exception as e:
        print(f'错误: {e}')

    start_nomachine()
    start_player()

    if is_install:
        print()
        print('完成！NoMachine 中文补丁已应用，Player 已启动。')
