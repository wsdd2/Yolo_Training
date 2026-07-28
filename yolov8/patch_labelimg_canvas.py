# -*- coding: utf-8 -*-
"""
一键修复 LabelImg + PyQt 的 canvas float TypeError。

问题来源：https://github.com/wsdd2/custom_canvas
典型报错：
  TypeError: drawLine(...): argument 1 has unexpected type 'float'

用法：
  python patch_labelimg_canvas.py            # 自动查找并打补丁
  python patch_labelimg_canvas.py --check    # 只检查，不修改
  python patch_labelimg_canvas.py --restore  # 从 .bak 还原
  python patch_labelimg_canvas.py --path C:\\...\\libs\\canvas.py

优先做「手术式」int() 修补（兼容不同 LabelImg 版本）；
若目标文件与仓库修复版高度一致，也可 --full 整文件替换。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR_FIXED = SCRIPT_DIR / "patches" / "labelimg_canvas_fixed.py"
GITHUB_RAW = "https://raw.githubusercontent.com/wsdd2/custom_canvas/main/canvas.py"

# (description, compiled pattern, replacement)
SURGICAL_FIXES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "crosshair drawLine X",
        re.compile(
            r"p\.drawLine\(\s*self\.prev_point\.x\(\)\s*,\s*0\s*,\s*"
            r"self\.prev_point\.x\(\)\s*,\s*self\.pixmap\.height\(\)\s*\)"
        ),
        "p.drawLine(int(self.prev_point.x()), 0, int(self.prev_point.x()), int(self.pixmap.height()))",
    ),
    (
        "crosshair drawLine Y",
        re.compile(
            r"p\.drawLine\(\s*0\s*,\s*self\.prev_point\.y\(\)\s*,\s*"
            r"self\.pixmap\.width\(\)\s*,\s*self\.prev_point\.y\(\)\s*\)"
        ),
        "p.drawLine(0, int(self.prev_point.y()), int(self.pixmap.width()), int(self.prev_point.y()))",
    ),
    (
        "drawing rect drawRect",
        re.compile(
            r"p\.drawRect\(\s*left_top\.x\(\)\s*,\s*left_top\.y\(\)\s*,\s*"
            r"rect_width\s*,\s*rect_height\s*\)"
        ),
        "p.drawRect(int(left_top.x()), int(left_top.y()), int(rect_width), int(rect_height))",
    ),
]


def _candidate_canvas_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        import labelImg  # type: ignore

        root = Path(labelImg.__file__).resolve().parent
        paths.append(root / "libs" / "canvas.py")
        paths.append(root / "canvas.py")
    except Exception:
        pass

    try:
        import site

        for sp in site.getsitepackages():
            paths.append(Path(sp) / "libs" / "canvas.py")
            paths.append(Path(sp) / "labelImg" / "libs" / "canvas.py")
    except Exception:
        pass

    # Common Windows / conda layouts
    for base in (
        Path(sys.prefix) / "Lib" / "site-packages",
        Path(sys.prefix) / "lib" / "site-packages",
        Path(r"C:\ProgramData\miniconda3\Lib\site-packages"),
        Path(r"C:\ProgramData\anaconda3\Lib\site-packages"),
    ):
        paths.append(base / "libs" / "canvas.py")
        paths.append(base / "labelImg" / "libs" / "canvas.py")

    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def find_canvas(explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        p = explicit.expanduser().resolve()
        return p if p.is_file() else None
    for p in _candidate_canvas_paths():
        if p.is_file():
            return p.resolve()
    return None


def is_already_patched(text: str) -> bool:
    return (
        "int(self.prev_point.x())" in text
        and "int(self.prev_point.y())" in text
        and "int(self.pixmap.height())" in text
    )


def needs_surgical_patch(text: str) -> bool:
    return any(pat.search(text) for _, pat, _ in SURGICAL_FIXES)


def backup_path(target: Path) -> Path:
    return target.with_suffix(target.suffix + ".bak")


def apply_surgical(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    out = text
    for name, pat, repl in SURGICAL_FIXES:
        new_out, n = pat.subn(repl, out)
        if n:
            applied.append(f"{name} x{n}")
            out = new_out
    return out, applied


def ensure_vendor_fixed() -> Path:
    if VENDOR_FIXED.is_file() and "int(self.prev_point.x())" in VENDOR_FIXED.read_text(
        encoding="utf-8", errors="ignore"
    ):
        return VENDOR_FIXED
    VENDOR_FIXED.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request

    print(f"[INFO] 下载修复版 canvas.py -> {VENDOR_FIXED}")
    print(f"       {GITHUB_RAW}")
    urllib.request.urlretrieve(GITHUB_RAW, VENDOR_FIXED)
    return VENDOR_FIXED


def patch_file(target: Path, *, full: bool = False) -> int:
    original = target.read_text(encoding="utf-8")
    bak = backup_path(target)

    if is_already_patched(original) and not needs_surgical_patch(original):
        print(f"[OK] 已打过补丁，无需修改: {target}")
        return 0

    if not bak.exists():
        shutil.copy2(target, bak)
        print(f"[INFO] 已备份: {bak}")
    else:
        print(f"[INFO] 备份已存在，保留原备份: {bak}")

    if full:
        fixed = ensure_vendor_fixed().read_text(encoding="utf-8")
        target.write_text(fixed, encoding="utf-8", newline="\n")
        print(f"[OK] 已用 custom_canvas 整文件替换: {target}")
        return 0

    new_text, applied = apply_surgical(original)
    if not applied:
        if is_already_patched(original):
            print(f"[OK] 已包含 int() 转换: {target}")
            return 0
        print("[WARN] 未匹配到已知未修补片段。")
        print("       可尝试: python patch_labelimg_canvas.py --full")
        return 2

    target.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"[OK] 手术式补丁已写入: {target}")
    for item in applied:
        print(f"     - {item}")
    return 0


def restore_file(target: Path) -> int:
    bak = backup_path(target)
    if not bak.is_file():
        print(f"[ERROR] 找不到备份: {bak}")
        return 1
    shutil.copy2(bak, target)
    print(f"[OK] 已从备份还原: {bak} -> {target}")
    return 0


def check_file(target: Path) -> int:
    text = target.read_text(encoding="utf-8")
    print(f"[INFO] canvas: {target}")
    if is_already_patched(text) and not needs_surgical_patch(text):
        print("[OK] 已修复（含 int(prev_point) / int(pixmap)）")
        return 0
    if needs_surgical_patch(text):
        print("[WARN] 仍存在未加 int() 的 drawLine/drawRect，需要打补丁")
        return 1
    print("[WARN] 无法确认是否已修复（文件结构可能与 LabelImg 旧版不同）")
    return 2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Patch LabelImg canvas.py float/PyQt TypeError")
    p.add_argument("--path", type=Path, default=None, help="explicit libs/canvas.py path")
    p.add_argument("--check", action="store_true", help="check only, do not modify")
    p.add_argument("--restore", action="store_true", help="restore from canvas.py.bak")
    p.add_argument(
        "--full",
        action="store_true",
        help="replace whole file with wsdd2/custom_canvas canvas.py",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    target = find_canvas(args.path)
    if target is None:
        print("[INFO] 当前环境未找到 LabelImg 的 libs/canvas.py。")
        print("       柜面分割标注用 labelme 时不需要此补丁。")
        print("       若之后安装了 LabelImg，再运行本脚本即可：")
        print("         pip install labelImg")
        print("         python patch_labelimg_canvas.py")
        if args.path is not None:
            print(f"[ERROR] 指定路径不存在: {args.path}")
            return 1
        return 0

    if args.check:
        return check_file(target)
    if args.restore:
        return restore_file(target)
    return patch_file(target, full=args.full)


if __name__ == "__main__":
    raise SystemExit(main())
