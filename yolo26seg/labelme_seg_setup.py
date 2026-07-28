# -*- coding: utf-8 -*-
"""
使用 labelme 对 train/val 图片进行 segments（多边形）标注的准备工作脚本。
- 从源目录复制 train、val 图片到 seg_dataset
- 生成 labelme 用的 labels.txt（类别：container, food, pot, slices）
- 可选：启动 labelme 进行标注，标注结果 .json 会保存在对应目录
"""
import os
import shutil
import subprocess
from pathlib import Path

# 源数据根目录（里面是图片）
source_root = r"E:\train_pot_1105_2\train_pot_1105_2\images"
# 分割标注数据集输出根目录（labelme 的 .json 也保存在此）
seg_dataset_root = r"E:\train_pot_1105_2\seg_dataset"
# labelme 类别（顺序对应后续若转 YOLO segment 时的 0,1,2,3）
class_names = ["container", "food", "pot", "slices"]

# 是否在准备完成后自动启动 labelme（先 train 后 val）
launch_labelme = True
# labelme 命令（pip 安装一般为 labelme；若找不到可改为绝对路径）
labelme_cmd = "labelme"
# =========================

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def copy_images(src_dir: Path, dst_dir: Path):
    """将 src_dir 下图片复制到 dst_dir，返回 (copied, skipped)。"""
    ensure_dir(dst_dir)
    copied, skipped = 0, 0
    for fp in sorted(src_dir.iterdir()):
        if not fp.is_file() or fp.suffix.lower() not in IMG_EXTS:
            continue
        dst = dst_dir / fp.name
        if dst.exists():
            skipped += 1
            continue
        shutil.copy2(fp, dst)
        copied += 1
    return copied, skipped


def write_labels_txt(seg_root: Path, names: list):
    """在 seg_dataset 根目录及 train/val 下写入 labels.txt，供 labelme 使用。"""
    content = "\n".join(names) + "\n"
    (seg_root / "labels.txt").write_text(content, encoding="utf-8")
    for sub in ("train", "val"):
        d = seg_root / sub
        if d.exists():
            (d / "labels.txt").write_text(content, encoding="utf-8")


def launch_labelme_ui(images_dir: Path, labels_file: Path, output_dir: Path):
    """
    启动 labelme 对指定目录进行多边形标注。
    --labels: 类别文件
    --output: 标注 json 保存目录（与图片同目录时可直接用 images_dir）
    """
    cmd = [
        labelme_cmd,
        str(images_dir),
        "--labels", str(labels_file),
        "--output", str(output_dir),
        # labelme>=7 已移除 --nodata；默认不写 imageData
    ]
    print("[INFO] 执行:", " ".join(cmd))
    print("[INFO] 在 labelme 中：用多边形（Polygon）勾选轮廓，保存后会在当前目录生成同名 .json")
    subprocess.run(cmd, check=False)


def main():
    src_root = Path(source_root)
    seg_root = Path(seg_dataset_root)

    if not src_root.exists():
        raise FileNotFoundError(f"源目录不存在: {src_root}")

    train_src = src_root / "train"
    val_src = src_root / "val"
    train_dst = seg_root / "train"
    val_dst = seg_root / "val"

    ensure_dir(seg_root)
    ensure_dir(train_dst)
    ensure_dir(val_dst)

    # 写入类别文件（根目录 + train/val 各一份，方便 labelme 打开子目录时也能读到）
    write_labels_txt(seg_root, class_names)
    print(f"[INFO] 已写入 labels.txt，类别: {class_names}")

    # 复制 train 图片
    if train_src.exists():
        c, s = copy_images(train_src, train_dst)
        print(f"[INFO] train 图片: 复制 {c} 张, 已存在跳过 {s} 张")
    else:
        print(f"[WARN] 未找到 train 目录: {train_src}")

    # 复制 val 图片
    if val_src.exists():
        c, s = copy_images(val_src, val_dst)
        print(f"[INFO] val 图片: 复制 {c} 张, 已存在跳过 {s} 张")
    else:
        print(f"[WARN] 未找到 val 目录: {val_src}")

    labels_file = seg_root / "labels.txt"

    if launch_labelme:
        # 先对 train 标注
        if train_src.exists() and any(train_dst.iterdir()):
            print("\n[INFO] 启动 labelme 标注 train 集...")
            launch_labelme_ui(train_dst, labels_file, train_dst)
        # 再对 val 标注
        if val_src.exists() and any(val_dst.iterdir()):
            print("\n[INFO] 启动 labelme 标注 val 集...")
            launch_labelme_ui(val_dst, labels_file, val_dst)

    print(f"\n[OK] 分割数据集目录: {seg_root}")
    print("     train 图片与 json:", train_dst)
    print("     val 图片与 json:", val_dst)
    print("     类别文件:", labels_file)


if __name__ == "__main__":
    main()
