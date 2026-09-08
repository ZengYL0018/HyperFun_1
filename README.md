# Gaussian NMR 化学位移标定工具

本项目用于从 Gaussian NMR 输出文件中提取 `Isotropic` 数据，按照 AD/NH3 参比进行化学位移标定，并可调用 Origin 自动生成 C、H、N 图。

## 功能

- 自动提取 `.log` 或 `.out` 文件中的：
  - 原子序号
  - 元素
  - `Isotropic` 数值
- 使用 AD 参比标定 C、H：
  - C：选择 AD 中数量最多的相似 C 数据组
  - H：使用 AD 中 H 数据的平均值
- 可选使用 NH3 参比标定 N
- 输出 Excel 可直接打开的 UTF-8 CSV
- 通过 Origin 模板自动生成 C、H、N 图
- C、H、N 使用不同模板：
  - `fig1.opju`：H
  - `fig2.opju`：C
  - `fig3.opju`：N
- Origin 图中峰高默认为 `0.6`
- C 图 X 轴范围为 `100–170 ppm`
- N 图 X 轴范围为 `50–270 ppm`
- H 图保留模板中的坐标轴设置

## 文件说明

| 文件 | 作用 |
|---|---|
| `script/extract_gaussian_isotropic.py` | 数据提取、参比计算和化学位移标定 |
| `script/nmr_gui.py` | 图形化操作界面 |
| `script/启动核磁标定界面.bat` | 双击启动 GUI |
| `script/plot_calibrated_nmr_origin.ps1` | 调用 Origin 并生成图 |
| `script/fig1.opju` | H 图模板 |
| `script/fig2.opju` | C 图模板 |
| `script/fig3.opju` | N 图模板 |

## 环境要求

- Windows
- Python 3.10 或更高版本
- Gaussian 输出文件
- 如需自动绘图：
  - Origin 2024 或兼容版本
  - Origin COM 自动化接口可用

本项目只使用 Python 标准库，不需要额外安装 Python 包。

## 图形界面使用

双击：

```text
script\启动核磁标定界面.bat
```

然后：

1. 选择样品 Gaussian 输出文件；
2. 选择 AD 参比文件；
3. 如需标定 N，勾选“使用 NH3 参比标定 N”，并选择 NH3 文件；
4. 选择 CSV 输出路径；
5. 如需绘图，勾选“同时调用 Origin 生成 `.opju`”；
6. 点击“开始处理”。

Origin 模板由程序自动使用，不需要在界面中选择模板。

## 命令行提取和标定

仅使用 AD 标定 C/H：

```powershell
python script\extract_gaussian_isotropic.py `
  "sample.log" `
  --ad-reference "ad-nmr.log" `
  -o "sample_calibrated.csv"
```

同时使用 NH3 标定 N：

```powershell
python script\extract_gaussian_isotropic.py `
  "sample.log" `
  --ad-reference "ad-nmr.log" `
  --nh3-reference "NH3-nmr.log" `
  -o "sample_calibrated.csv"
```

## 标定公式

```text
标定化学位移
= 参比平均 Isotropic
  - 样品 Isotropic
  + 真实参比化学位移
```

当前真实参比化学位移：

| 元素 | 真实参比化学位移 |
|---|---:|
| C | 38.5 ppm |
| H | 1.8 ppm |
| N | 0.0 ppm |

O 不参与当前标定。

## Origin 输出

启用 Origin 绘图后，程序会分别生成：

```text
sample_C.opju
sample_H.opju
sample_N.opju
```

实际只会生成 CSV 中存在标定数据的元素图。

每个图均会：

1. 使用对应的 `fig*.opju` 模板；
2. 清空模板中的旧数据；
3. 保留模板的图层、坐标轴、字体和其他作图参数；
4. 写入当前样品数据；
5. 使用固定峰高 `0.6`；
6. 使用样品文件名更新图名。

## CSV 输出列

输出 CSV 包含：

- `文件`
- `原子序号`
- `元素`
- `Isotropic (ppm)`
- `参比平均 Isotropic (ppm)`
- `真实参比化学位移 (ppm)`
- `标定化学位移 (ppm)`
- `原始行`

O 或没有对应参比的数据，其标定列会留空。

## 常见问题

### Origin 图中没有谱线

请确认：

- `fig1.opju`、`fig2.opju`、`fig3.opju` 位于 `script` 文件夹；
- 模板的工作表和图层数据列与脚本约定一致；
- CSV 中对应元素存在“标定化学位移”；
- Origin 已正确安装并可启动。

### 不需要 N 标定怎么办？

不勾选 NH3 选项即可。程序仍会标定 C/H，N 的标定列留空。

### 只想生成 CSV 怎么办？

不要勾选 Origin 绘图选项，程序只输出 CSV，不启动 Origin。
