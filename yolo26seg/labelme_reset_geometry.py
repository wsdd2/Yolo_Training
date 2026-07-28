# -*- coding: utf-8 -*-
"""
在启动 labelme 前清除已保存的窗口位置/大小，避免双屏时窗口自动占满两屏。
用法：与 labelme_normal.py 相同，例如：
  python labelme_reset_geometry.py --source E:\\images --output E:\\annotations --classes E:\\class_names.txt
首次用本脚本启动后，请将 labelme 窗口拖到目标屏幕并最大化，再关闭，之后即可用普通方式启动。
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 保证与 labelme_normal.py 同目录时可导入
sys.path.insert(0, str(Path(__file__).resolve().parent))
from labelme_normal import check_labelme_env, read_class_names


def _config_paths():
    """返回可能存在的 .labelmerc 路径（Windows / 通用）。"""
    paths = []
    if os.name == "nt":
        for env in ("USERPROFILE", "LOCALAPPDATA", "APPDATA"):
            p = os.environ.get(env)
            if p:
                paths.append(Path(p) / ".labelmerc")
    else:
        paths.append(Path.home() / ".labelmerc")
    return [p for p in paths if p.exists()]


def _remove_labelme_registry_geometry():
    """尝试删除 Windows 注册表中 labelme 保存的窗口几何。"""
    if os.name != "nt":
        return
    try:
        import winreg
    except ImportError:
        return
    # 常见可能保存 geometry 的键
    keys_to_try = [
        (winreg.HKEY_CURRENT_USER, r"Software\labelme"),
        (winreg.HKEY_CURRENT_USER, r"Software\wkentaro\labelme"),
    ]
    for hkey, subkey in keys_to_try:
        try:
            with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_ALL_ACCESS) as k:
                for name in ("geometry", "windowState", "state"):
                    try:
                        winreg.DeleteValue(k, name)
                    except OSError:
                        pass
        except OSError:
            pass


def reset_labelme_geometry():
    """备份并移除 .labelmerc，并尝试清除注册表中的窗口几何。"""
    backed = []
    for path in _config_paths():
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(path, bak)
            path.unlink()
            backed.append((path, bak))
            print(f"[OK] 已备份并移除: {path} -> {bak}")
        except Exception as e:
            print(f"[WARN] 无法处理 {path}: {e}")

    _remove_labelme_registry_geometry()
    if backed:
        print("[INFO] 窗口将使用默认尺寸打开，请拖到目标屏幕后最大化再关闭。")
    return backed


def main():
    parser = argparse.ArgumentParser(
        description="清除 labelme 已保存的窗口几何后启动 labelme，避免双屏占满。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", "-s", required=True, type=Path, help="图片所在目录")
    parser.add_argument("--output", "-o", required=True, type=Path, help="标注结果 .json 的保存目录")
    parser.add_argument("--classes", "-c", required=True, type=Path, help="类别文件路径")
    parser.add_argument(
        "--labelme-cmd", default="labelme", help="labelme 可执行命令",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="不清除几何，仅按参数启动 labelme（与 labelme_normal 行为一致）",
    )
    args = parser.parse_args()

    if not args.no_reset:
        reset_labelme_geometry()

    # 与 labelme_normal 一致的环境与参数校验
    if args.labelme_cmd == "labelme":
        ok, cmd = check_labelme_env()
        if not ok:
            sys.exit(1)
        labelme_argv = cmd.split() if " " in cmd else [cmd]
    else:
        labelme_argv = args.labelme_cmd.split() if " " in args.labelme_cmd else [args.labelme_cmd]
        print(f"[INFO] 使用指定命令: {args.labelme_cmd}")

    if not args.source.exists() or not args.source.is_dir():
        print(f"[ERROR] 源目录不存在或不是目录: {args.source}")
        sys.exit(1)
    try:
        read_class_names(args.classes)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    args.output.mkdir(parents=True, exist_ok=True)

    cmd = [
        *labelme_argv,
        str(args.source.resolve()),
        "--labels", str(args.classes.resolve()),
        "--output", str(args.output.resolve()),
    ]
    print("[INFO] 执行:", " ".join(cmd))
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
