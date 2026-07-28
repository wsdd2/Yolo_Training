# -*- coding: utf-8 -*-
"""
柜面 YOLO26-seg 标注启动脚本（labelme 多边形手动标注）。

数据根目录默认：E:/MscapeTech/dataset  （WSL 下即 /mnt/e/MscapeTech/dataset）
类别与 YOLOE / ROS2 发布名对齐，见同目录 cabinet_controls_seg_classes.txt。

用法（Windows）：
  cd E:\\MscapeTech\\Yolo_Training\\yolo26seg
  python launch_cabinet_labelme.py

用法（WSL）：
  cd /mnt/e/MscapeTech/Yolo_Training/yolo26seg
  python launch_cabinet_labelme.py

可选参数：
  --dataset   数据根目录
  --no-launch 只准备 labels.txt / 统计，不启动 labelme
  --flags     使用 flags 模式（多标签勾选）；默认 labels 单选类别
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# =============================================================================
# 默认配置
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CLASSES_FILE = SCRIPT_DIR / "cabinet_controls_seg_classes.txt"

# Windows / WSL 同源路径
DEFAULT_DATASET_ROOT = Path(r"E:/MscapeTech/dataset")
if not DEFAULT_DATASET_ROOT.exists():
    wsl_candidate = Path("/mnt/e/MscapeTech/dataset")
    if wsl_candidate.exists():
        DEFAULT_DATASET_ROOT = wsl_candidate

# 与 YOLOE prompt / ROS2 Object2D.class_name 一致（顺序即 class_id）
DEFAULT_CLASS_NAMES = [
    "red push button",
    "green push button",
    "black rotary selector switch",
    "yellow toggle switch",
    "red toggle switch",
    "white toggle switch",
    "black cabinet door handle",
    "lock point",
]

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _load_class_names(path: Path) -> list[str]:
    if not path.is_file():
        return list(DEFAULT_CLASS_NAMES)
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line)
    return names or list(DEFAULT_CLASS_NAMES)


def _resolve_labelme_cmd() -> list[str]:
    """Prefer `labelme` on PATH; fall back to `python -m labelme`."""
    exe = shutil.which("labelme")
    if exe:
        return [exe]
    return [sys.executable, "-m", "labelme"]


def _count_images(root: Path) -> list[Path]:
    files: list[Path] = []
    for fp in sorted(root.iterdir()):
        if fp.is_file() and fp.suffix.lower() in IMG_EXTS:
            files.append(fp)
    return files


def _count_json(root: Path) -> int:
    return sum(1 for fp in root.iterdir() if fp.is_file() and fp.suffix.lower() == ".json")


def write_labels_txt(dataset_root: Path, class_names: list[str]) -> Path:
    content = "\n".join(class_names) + "\n"
    out = dataset_root / "labels.txt"
    out.write_text(content, encoding="utf-8")
    return out


def write_class_id_map(dataset_root: Path, class_names: list[str]) -> Path:
    """Human-readable id map for later YOLO convert / ROS publish checks."""
    lines = [f"{i}: {name}" for i, name in enumerate(class_names)]
    out = dataset_root / "class_id_map.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def launch_labelme(images_dir: Path, labels_file: Path, *, use_flags: bool = False) -> int:
    cmd = _resolve_labelme_cmd() + [
        str(images_dir),
        "--nodata",
        "--output",
        str(images_dir),
    ]
    if use_flags:
        cmd.extend(["--flags", str(labels_file)])
    else:
        cmd.extend(["--labels", str(labels_file)])

    print("[INFO] 执行:", " ".join(cmd))
    print("[INFO] 标注提示：")
    print("       1) Create Polygons 勾选部件轮廓（旋转视角也请贴合外形）")
    print("       2) 类别必须从列表选择，勿手打别名")
    print("       3) 保存后生成与图片同名的 .json（--nodata，不含 imageData）")
    print("       4) lock point 标红贴/锁点区域；handle 标整段黑色手柄")
    try:
        completed = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print(
            "[ERROR] 未找到 labelme。请先安装：\n"
            "        pip install labelme\n"
            "        或：python -m pip install labelme"
        )
        return 1
    return int(completed.returncode)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Launch labelme for cabinet YOLO26-seg labeling")
    p.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help=f"image + json root (default: {DEFAULT_DATASET_ROOT})",
    )
    p.add_argument(
        "--classes-file",
        type=Path,
        default=DEFAULT_CLASSES_FILE,
        help="class list file (YOLOE-aligned names)",
    )
    p.add_argument(
        "--no-launch",
        action="store_true",
        help="only write labels.txt / print stats, do not start labelme",
    )
    p.add_argument(
        "--flags",
        action="store_true",
        help="pass class file as --flags instead of --labels",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = args.dataset.expanduser().resolve()
    if not dataset_root.is_dir():
        print(f"[ERROR] 数据目录不存在: {dataset_root}")
        print("        请把图片放到该目录，或用 --dataset 指定路径。")
        return 1

    class_names = _load_class_names(args.classes_file.expanduser().resolve())
    labels_file = write_labels_txt(dataset_root, class_names)
    id_map_file = write_class_id_map(dataset_root, class_names)

    images = _count_images(dataset_root)
    n_json = _count_json(dataset_root)
    print(f"[INFO] dataset   : {dataset_root}")
    print(f"[INFO] images    : {len(images)}")
    print(f"[INFO] json done : {n_json}")
    print(f"[INFO] labels.txt: {labels_file}")
    print(f"[INFO] id map    : {id_map_file}")
    print("[INFO] classes (ROS2 / YOLOE aligned):")
    for i, name in enumerate(class_names):
        print(f"       {i}: {name}")

    if not images:
        print("[WARN] 目录下没有图片，仍写入了 labels.txt，请先放入待标注图。")
        return 0

    if args.no_launch:
        print("[OK] --no-launch：准备完成，未启动 labelme。")
        return 0

    return launch_labelme(dataset_root, labels_file, use_flags=args.flags)


if __name__ == "__main__":
    raise SystemExit(main())
