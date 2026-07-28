# -*- coding: utf-8 -*-
"""
通用 labelme 标注脚本：通过 CLI 指定源目录、输出目录和类别文件，检查环境后启动 labelme。
用法示例:
  python labelme_normal.py --source E:\\images --output E:\\annotations --classes E:\\class_names.txt
"""
import argparse
import subprocess
import sys
from pathlib import Path


def check_labelme_env():
    """
    检查 labelme 是否已正确安装，若未安装则打印说明并退出。
    返回 (success: bool, labelme_cmd: str)
    """
    for cmd in ("labelme", "labelme.exe"):
        found = None
        try:
            found = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            continue
        if found.returncode == 0 or "labelme" in (found.stdout or "") or "labelme" in (found.stderr or ""):
            print(f"[OK] labelme 已安装，命令: {cmd}")
            return True, cmd
        # 有些版本 --version 可能非 0，只要能跑就行
        if found.returncode is not None:
            print(f"[OK] labelme 已安装，命令: {cmd}")
            return True, cmd

    # 尝试通过 python -m labelme 检查
    try:
        r = subprocess.run(
            [sys.executable, "-m", "labelme", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0 or "labelme" in (r.stdout or r.stderr or ""):
            print("[OK] labelme 已安装（通过 python -m labelme）")
            return True, f"{sys.executable} -m labelme"
    except Exception:
        pass

    print("[ERROR] 未检测到 labelme，请先安装：")
    print("  pip install labelme")
    print("安装后请确认在终端中可执行: labelme --version")
    return False, ""


def read_class_names(path: Path):
    """从 class_names.txt 读取类别列表（每行一个，忽略空行和 # 注释）。"""
    if not path.exists():
        raise FileNotFoundError(f"类别文件不存在: {path}")
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    if not lines:
        raise ValueError(f"类别文件为空或仅有注释: {path}")
    return lines


def main():
    parser = argparse.ArgumentParser(
        description="通用 labelme 标注：指定源目录、输出目录和类别文件，检查环境后启动 labelme。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source", "-s",
        required=True,
        type=Path,
        help="图片所在目录（labelme 将打开此目录进行标注）",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        type=Path,
        help="标注结果 .json 的保存目录",
    )
    parser.add_argument(
        "--classes", "-c",
        required=True,
        type=Path,
        help="类别文件路径（每行一个类别名，支持 # 注释）",
    )
    parser.add_argument(
        "--labelme-cmd",
        default="labelme",
        help="labelme 可执行命令（若不在 PATH 中可写绝对路径或 python -m labelme）",
    )
    args = parser.parse_args()

    # 1. 检查 labelme 环境（若用户未指定 --labelme-cmd 则用自动检测的）
    if args.labelme_cmd == "labelme":
        ok, cmd = check_labelme_env()
        if not ok:
            sys.exit(1)
        # 若检测到的是 "python -m labelme"，需要拆成列表
        if " " in cmd:
            labelme_argv = cmd.split()
        else:
            labelme_argv = [cmd]
    else:
        labelme_argv = args.labelme_cmd.split() if " " in args.labelme_cmd else [args.labelme_cmd]
        print(f"[INFO] 使用指定命令: {args.labelme_cmd}")

    # 2. 校验参数
    if not args.source.exists():
        print(f"[ERROR] 源目录不存在: {args.source}")
        sys.exit(1)
    if not args.source.is_dir():
        print(f"[ERROR] 源路径不是目录: {args.source}")
        sys.exit(1)

    try:
        class_names = read_class_names(args.classes)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    print(f"[INFO] 已加载 {len(class_names)} 个类别: {class_names}")

    args.output.mkdir(parents=True, exist_ok=True)
    labels_path = args.classes.resolve()

    # 3. 启动 labelme
    cmd = [
        *labelme_argv,
        str(args.source.resolve()),
        "--labels", str(labels_path),
        "--output", str(args.output.resolve()),
    ]
    print("[INFO] 执行:", " ".join(cmd))
    print("[INFO] 在 labelme 中用多边形（Polygon）勾选轮廓，保存后会在输出目录生成同名 .json")
    subprocess.run(cmd, check=False)
    print(f"\n[OK] 标注结果将保存到: {args.output}")


if __name__ == "__main__":
    main()
