param(
    [Parameter(Mandatory = $true)][string]$InputPdf,
    [Parameter(Mandatory = $true)][string]$OutputTxt,
    [string]$Poppler = 'C:\Users\parkd\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Await-Result($AsyncOperation, [Type]$ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($AsyncOperation))
    $task.Wait()
    return $task.Result
}

$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]

$resolvedPdf = (Resolve-Path -LiteralPath $InputPdf).Path
$resolvedOutputDir = Split-Path -Parent $OutputTxt
if (-not (Test-Path -LiteralPath $resolvedOutputDir)) {
    New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null
}
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('transport-gap-ocr-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $prefix = Join-Path $tempRoot 'page'
    & $Poppler -png -r 160 -scale-to 3000 -q $resolvedPdf $prefix
    if ($LASTEXITCODE -ne 0) { throw "pdftoppm failed with exit code $LASTEXITCODE" }

    $language = New-Object 'Windows.Globalization.Language' -ArgumentList 'ko'
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
    if ($null -eq $engine) { throw 'Korean Windows OCR engine is unavailable.' }

    $output = New-Object System.Collections.Generic.List[string]
    $images = Get-ChildItem -LiteralPath $tempRoot -Filter 'page-*.png' | Sort-Object Name
    foreach ($image in $images) {
        $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($image.FullName)) ([Windows.Storage.StorageFile])
        $stream = Await-Result ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        try {
            $decoder = Await-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
            $bitmap = Await-Result ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
            try {
                $result = Await-Result ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
                $pageNumber = [int]([regex]::Match($image.BaseName, '(\d+)$').Groups[1].Value)
                $output.Add("=== PDF p.$pageNumber ===")
                $output.Add($result.Text)
                $output.Add('')
            }
            finally {
                if ($null -ne $bitmap) { $bitmap.Dispose() }
            }
        }
        finally {
            if ($null -ne $stream) { $stream.Dispose() }
        }
    }
    [System.IO.File]::WriteAllLines($OutputTxt, $output, [System.Text.UTF8Encoding]::new($false))
    [pscustomobject]@{
        pages = $images.Count
        chars = ([System.IO.File]::ReadAllText($OutputTxt)).Length
        output = $OutputTxt
    } | ConvertTo-Json -Compress
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
