r"""Extract Gaussian NMR isotropic shielding values into a CSV table.

Examples:
    python extract_gaussian_isotropic.py "path\calculation.log"
    python extract_gaussian_isotropic.py "path\logs" -o isotropic.csv
    python extract_gaussian_isotropic.py "2NH2PBI-nmr.log" --ad-reference "ad-nmr.log" \
        --nh3-reference "NH3-nmr.log" -o calibrated.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


ISOTROPIC_PATTERN = re.compile(
    r"^\s*(?P<atom_number>\d+)\s+(?P<element>[A-Za-z]{1,3})\s+"
    r"Isotropic\s*=\s*(?P<isotropic>[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][+-]?\d+)?)\b"
)


def find_log_files(inputs: list[Path]) -> list[Path]:
    """Expand files/directories and return unique Gaussian log files."""
    files: list[Path] = []
    seen: set[Path] = set()

    for input_path in inputs:
        if input_path.is_file():
            candidates = [input_path]
        elif input_path.is_dir():
            candidates = sorted(
                path
                for path in input_path.rglob("*")
                if path.is_file() and path.suffix.lower() in {".log", ".out"}
            )
        else:
            raise FileNotFoundError(f"输入路径不存在: {input_path}")

        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(candidate)

    return files


def extract_isotropic(log_path: Path) -> list[dict[str, object]]:
    """Extract atom number, element, and isotropic value from one log file."""
    rows: list[dict[str, object]] = []
    with log_path.open("r", encoding="utf-8", errors="replace") as log_file:
        for line_number, line in enumerate(log_file, start=1):
            match = ISOTROPIC_PATTERN.search(line)
            if not match:
                continue

            value_text = match.group("isotropic").replace("D", "E").replace("d", "e")
            rows.append(
                {
                    "文件": log_path.name,
                    "原子序号": int(match.group("atom_number")),
                    "元素": match.group("element"),
                    "Isotropic (ppm)": float(value_text),
                    "原始行": line_number,
                }
            )
    return rows


def average(values: list[float]) -> float:
    if not values:
        raise ValueError("没有可用于计算平均值的 Isotropic 数据。")
    return sum(values) / len(values)


def reference_averages(
    ad_rows: list[dict[str, object]],
    nh3_rows: list[dict[str, object]] | None = None,
) -> dict[str, float]:
    """Calculate shielding averages used for C/H/N calibration."""
    ad_by_element: dict[str, list[float]] = {"C": [], "H": []}
    for row in ad_rows:
        element = str(row["元素"])
        if element in ad_by_element:
            ad_by_element[element].append(float(row["Isotropic (ppm)"]))

    if not ad_by_element["C"] or not ad_by_element["H"]:
        raise ValueError("ad-nmr 需要同时包含 C 和 H 的 Isotropic 数据。")

    # Adamantane C values can contain several chemical environments. Use the
    # most populated cluster, as requested, rather than averaging all C atoms.
    carbon_values = sorted(ad_by_element["C"])
    best_cluster: list[float] = []
    for start in range(len(carbon_values)):
        for end in range(start + len(best_cluster) + 1, len(carbon_values) + 1):
            cluster = carbon_values[start:end]
            if cluster[-1] - cluster[0] <= 2.0:
                best_cluster = cluster
            else:
                break
    if len(best_cluster) < 2:
        raise ValueError("ad-nmr 中无法识别数量较多的相似 C 数据。")

    references = {
        "C": average(best_cluster),
        "H": average(ad_by_element["H"]),
    }
    if nh3_rows is not None:
        nh3_n_values = [
            float(row["Isotropic (ppm)"]) for row in nh3_rows if row["元素"] == "N"
        ]
        if not nh3_n_values:
            raise ValueError("NH3-nmr 中没有 N 的 Isotropic 数据。")
        references["N"] = average(nh3_n_values)
    return references


def calibrate_rows(
    rows: list[dict[str, object]], reference_averages_by_element: dict[str, float]
) -> list[dict[str, object]]:
    """Apply: reference average - sample shielding + true reference shift."""
    true_reference_shifts = {"C": 38.5, "H": 1.8, "N": 0.0}
    calibrated: list[dict[str, object]] = []
    for row in rows:
        element = str(row["元素"])
        output_row = dict(row)
        if element in reference_averages_by_element:
            shielding = float(row["Isotropic (ppm)"])
            reference_average = reference_averages_by_element[element]
            output_row["参比平均 Isotropic (ppm)"] = round(reference_average, 4)
            output_row["真实参比化学位移 (ppm)"] = true_reference_shifts[element]
            output_row["标定化学位移 (ppm)"] = round(
                reference_average - shielding + true_reference_shifts[element], 4
            )
        else:
            output_row["参比平均 Isotropic (ppm)"] = ""
            output_row["真实参比化学位移 (ppm)"] = ""
            output_row["标定化学位移 (ppm)"] = ""
        calibrated.append(output_row)
    return calibrated


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    """Write rows with UTF-8 BOM so Chinese headers display correctly in Excel."""
    fieldnames = [
        "文件",
        "原子序号",
        "元素",
        "Isotropic (ppm)",
        "参比平均 Isotropic (ppm)",
        "真实参比化学位移 (ppm)",
        "标定化学位移 (ppm)",
        "原始行",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 Gaussian 输出文件中提取 NMR Isotropic 数值并输出 CSV 表格。"
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="一个或多个 .log/.out 文件，或包含这些文件的目录（目录会递归搜索）。",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("isotropic_values.csv"),
        help="输出 CSV 文件路径（默认：isotropic_values.csv）。",
    )
    parser.add_argument(
        "--ad-reference",
        type=Path,
        help="AD 参比 Gaussian 输出文件，用于 C/H 标定。",
    )
    parser.add_argument(
        "--nh3-reference",
        type=Path,
        help="NH3 参比 Gaussian 输出文件，用于 N 标定。",
    )
    parser.add_argument(
        "--origin-template",
        type=Path,
        help="Origin .opju 模板；提供后自动更新模板并生成 Origin 图。",
    )
    parser.add_argument(
        "--origin-output",
        type=Path,
        help="自动生成的 Origin .opju 路径（默认与 CSV 同名）。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        log_files = find_log_files(args.inputs)
        if not log_files:
            raise ValueError("没有找到 .log 或 .out 文件。")

        rows: list[dict[str, object]] = []
        for log_file in log_files:
            rows.extend(extract_isotropic(log_file))

        if not rows:
            raise ValueError("找到输出文件，但没有匹配到 Isotropic = 数值。")

        if args.nh3_reference and not args.ad_reference:
            raise ValueError("使用 --nh3-reference 时必须同时提供 --ad-reference。")
        if args.ad_reference:
            ad_rows = extract_isotropic(args.ad_reference)
            nh3_rows = (
                extract_isotropic(args.nh3_reference)
                if args.nh3_reference
                else None
            )
            references = reference_averages(ad_rows, nh3_rows)
            rows = calibrate_rows(rows, references)

        write_csv(rows, args.output)
        if args.origin_template:
            if not args.ad_reference:
                raise ValueError("自动绘图需要提供 --ad-reference。")
            script_path = Path(__file__).with_name("plot_calibrated_nmr_origin.ps1")
            origin_output = args.origin_output or args.output.with_suffix(".opju")
            command = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path.resolve()),
                "-CsvPath",
                str(args.output.resolve()),
                "-TemplatePath",
                str(args.origin_template.resolve()),
                "-OutputOpju",
                str(origin_output.resolve()),
            ]
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip())
            print(result.stdout.strip())
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1

    print(f"已提取 {len(rows)} 条记录，输出至: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
