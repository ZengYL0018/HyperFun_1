"""Graphical interface for Gaussian NMR extraction and calibration."""

from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import extract_gaussian_isotropic as extractor


class NmrApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Gaussian NMR 化学位移标定")
        self.root.geometry("760x430")
        self.root.minsize(680, 380)

        self.sample = tk.StringVar()
        self.ad_reference = tk.StringVar()
        self.nh3_reference = tk.StringVar()
        self.output_csv = tk.StringVar()
        self.origin_output = tk.StringVar()
        self.use_nh3 = tk.BooleanVar(value=False)
        self.use_origin = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="请选择文件，然后点击“开始处理”。")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        self._file_row(frame, 0, "样品 Gaussian 输出", self.sample, ".log")
        self._file_row(frame, 1, "AD 参比输出", self.ad_reference, ".log")

        nh3_check = ttk.Checkbutton(
            frame,
            text="使用 NH3 参比标定 N",
            variable=self.use_nh3,
            command=self._toggle_nh3,
        )
        nh3_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(8, 2))
        self.nh3_entry = self._file_row(
            frame, 3, "NH3 参比输出", self.nh3_reference, ".log"
        )

        ttk.Separator(frame).grid(row=4, column=0, columnspan=3, sticky="ew", pady=12)
        self._file_row(frame, 5, "输出 CSV", self.output_csv, ".csv", save=True)

        origin_check = ttk.Checkbutton(
            frame,
            text="同时调用 Origin 生成 .opju",
            variable=self.use_origin,
            command=self._toggle_origin,
        )
        origin_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(8, 2))
        self.origin_output_entry = self._file_row(
            frame, 7, "Origin 输出项目", self.origin_output, ".opju", save=True
        )

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=8, column=0, columnspan=3, pady=18)
        self.run_button = ttk.Button(
            button_frame, text="开始处理", command=self._start
        )
        self.run_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空", command=self._clear).pack(
            side=tk.LEFT, padx=5
        )

        ttk.Label(
            frame, textvariable=self.status, foreground="#555555", wraplength=700
        ).grid(row=9, column=0, columnspan=3, sticky=tk.W)
        self._toggle_nh3()
        self._toggle_origin()

    def _file_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        suffix: str,
        save: bool = False,
    ) -> ttk.Entry:
        ttk.Label(parent, text=label, width=19).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=6, pady=5)
        button = ttk.Button(
            parent,
            text="浏览",
            command=lambda: self._browse(variable, suffix, save),
        )
        button.grid(row=row, column=2, pady=5)
        return entry

    def _browse(self, variable: tk.StringVar, suffix: str, save: bool) -> None:
        if save:
            path = filedialog.asksaveasfilename(
                defaultextension=suffix,
                filetypes=[(suffix.upper()[1:] + " 文件", "*" + suffix), ("所有文件", "*.*")],
            )
        else:
            path = filedialog.askopenfilename(
                filetypes=[("Gaussian/Origin 文件", "*.log *.out *.opju"), ("所有文件", "*.*")]
            )
        if path:
            variable.set(path)

    def _toggle_nh3(self) -> None:
        state = tk.NORMAL if self.use_nh3.get() else tk.DISABLED
        self.nh3_entry.configure(state=state)

    def _toggle_origin(self) -> None:
        state = tk.NORMAL if self.use_origin.get() else tk.DISABLED
        self.origin_output_entry.configure(state=state)

    def _clear(self) -> None:
        for variable in (
            self.sample,
            self.ad_reference,
            self.nh3_reference,
            self.output_csv,
            self.origin_output,
        ):
            variable.set("")
        self.status.set("已清空。")

    def _start(self) -> None:
        sample = Path(self.sample.get().strip())
        ad = Path(self.ad_reference.get().strip())
        if not sample.is_file() or not ad.is_file():
            messagebox.showerror("输入错误", "请选择有效的样品和 AD 参比文件。")
            return
        if self.use_nh3.get() and not Path(self.nh3_reference.get()).is_file():
            messagebox.showerror("输入错误", "已勾选 NH3，请选择有效的 NH3 参比文件。")
            return
        output = Path(self.output_csv.get().strip() or sample.with_name(
            sample.stem + "_calibrated.csv"
        ))
        self.output_csv.set(str(output))
        self.run_button.configure(state=tk.DISABLED)
        self.status.set("处理中，请稍候……")
        threading.Thread(target=self._process, daemon=True).start()

    def _process(self) -> None:
        try:
            rows = extractor.extract_isotropic(Path(self.sample.get()))
            ad_rows = extractor.extract_isotropic(Path(self.ad_reference.get()))
            nh3_rows = (
                extractor.extract_isotropic(Path(self.nh3_reference.get()))
                if self.use_nh3.get()
                else None
            )
            rows = extractor.calibrate_rows(
                rows, extractor.reference_averages(ad_rows, nh3_rows)
            )
            output = Path(self.output_csv.get())
            extractor.write_csv(rows, output)

            if self.use_origin.get():
                origin_output = Path(
                    self.origin_output.get().strip() or output.with_suffix(".opju")
                )
                script = Path(__file__).with_name("plot_calibrated_nmr_origin.ps1")
                command = [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(script), "-CsvPath", str(output),
                    "-OutputOpju", str(origin_output),
                ]
                result = subprocess.run(
                    command, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", check=False,
                )
                if result.returncode:
                    raise RuntimeError(result.stderr.strip() or result.stdout.strip())
                origin_message = result.stdout.strip() or str(origin_output)
                message = f"完成：CSV + Origin 项目\n{output}\n{origin_message}"
            else:
                message = f"完成：CSV\n{output}"
            self.root.after(0, self._done, message)
        except (OSError, ValueError, RuntimeError) as error:
            self.root.after(0, self._failed, str(error))

    def _done(self, message: str) -> None:
        self.run_button.configure(state=tk.NORMAL)
        self.status.set(message)
        messagebox.showinfo("处理完成", message)

    def _failed(self, message: str) -> None:
        self.run_button.configure(state=tk.NORMAL)
        self.status.set("处理失败。")
        messagebox.showerror("处理失败", message)


def main() -> None:
    root = tk.Tk()
    NmrApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
