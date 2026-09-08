param(
    [Parameter(Mandatory = $true)]
    [string]$CsvPath,
    [string]$OutputOpju,
    [double]$PeakHeight = 0.6
)

$ErrorActionPreference = "Stop"
$templateByElement = @{
    H = Join-Path $PSScriptRoot "fig1.opju"
    C = Join-Path $PSScriptRoot "fig2.opju"
    N = Join-Path $PSScriptRoot "fig3.opju"
}

if (-not $OutputOpju) {
    $OutputOpju = [System.IO.Path]::ChangeExtension($CsvPath, ".opju")
}

if (-not (Test-Path -LiteralPath $CsvPath -PathType Leaf)) {
    throw "CSV 文件不存在: $CsvPath"
}
$rows = Import-Csv -LiteralPath $CsvPath
$sampleName = [System.IO.Path]::GetFileNameWithoutExtension([string]$rows[0].文件)
$elementRows = @{}
foreach ($candidate in $rows) {
    $candidateProperties = @($candidate.PSObject.Properties)
    $element = [string]$candidateProperties[2].Value
    if ($element -in @("C", "H", "N") -and $candidateProperties[6].Value -ne "") {
        if (-not $elementRows.ContainsKey($element)) {
            $elementRows[$element] = @()
        }
        $elementRows[$element] += $candidate
    }
}
$elements = @($elementRows.Keys | Sort-Object)
if ($elements.Count -eq 0) {
    throw "CSV has no calibrated C, H, or N shifts to plot."
}

foreach ($element in $elements) {
    $templatePath = $templateByElement[$element]
    if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
        throw "元素 $element 的内置 Origin 模板不存在: $templatePath"
    }

    $plotRows = @($elementRows[$element] | Sort-Object {
        $candidateProperties = @($_.PSObject.Properties)
        [int]$candidateProperties[1].Value
    })
    # Write label, chemical shift, and peak height directly without a blank
    # leading column.
    $matrix = New-Object 'object[,]' $plotRows.Count, 3
    for ($i = 0; $i -lt $plotRows.Count; $i++) {
        $row = $plotRows[$i]
        $properties = @($row.PSObject.Properties)
        $matrix[$i, 0] = "{0}  {1}" -f $properties[1].Value, $properties[2].Value
        $matrix[$i, 1] = [double]$properties[6].Value
        $matrix[$i, 2] = $PeakHeight
    }

    $base = [System.IO.Path]::GetFileNameWithoutExtension($OutputOpju)
    $extension = [System.IO.Path]::GetExtension($OutputOpju)
    $directory = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($OutputOpju))
    $elementOutput = Join-Path $directory ($base + "_" + $element + $extension)

    $origin = New-Object -ComObject Origin.ApplicationSI
    try {
        $outputOpjuFull = [System.IO.Path]::GetFullPath($elementOutput)
        Copy-Item -LiteralPath $templatePath -Destination $outputOpjuFull -Force
        $origin.Visible = $true
        if (-not $origin.Load($outputOpjuFull)) {
            throw "Origin could not open the template project."
        }
        $origin.Execute("win -a Book1; wks.clear();")
        $origin.PutWorksheet("Book1", $matrix)
        $escapedSampleName = ($sampleName + " " + $element).Replace('"', '\"')
        $origin.Execute(
             "page -a Graph1; page.name$=""$escapedSampleName""; " +
             "page.longname$=""$escapedSampleName""; " +
             "label -s -n title ""$escapedSampleName""; layer -a;"
        )
        if ($element -eq "C") {
            $origin.Execute("layer.x.from=100; layer.x.to=170;")
        }
        elseif ($element -eq "N") {
            $origin.Execute("layer.x.from=50; layer.x.to=270;")
        }
        $origin.Save()
        Write-Output "已生成 $element 图: $outputOpjuFull"
    }
    finally {
        if ($origin) {
            $origin.Exit()
        }
    }
}
