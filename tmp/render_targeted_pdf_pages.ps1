$ErrorActionPreference = 'Stop'
$poppler = 'C:\Users\parkd\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe'
$outDir = Join-Path $PSScriptRoot 'pdf_targeted_qa'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$items = @(
    @{ Name = 'E1_A10_p1'; File = '미사강변도시 A24블록 10년 공공임대주택리츠 입주자 모집.pdf'; Page = 1 },
    @{ Name = 'E2_C07_p2'; File = '250724(석간) 3기 신도시 남양주왕숙 첫 공급 개시(공공택지관리과).pdf'; Page = 2 },
    @{ Name = 'E2_C09_p4'; File = '(정정)(정정)고양창릉S-4블록공공분양입주자모집공고문.pdf'; Page = 4 },
    @{ Name = 'E2_C09_S3_p5'; File = '(정정)(정정)고양창릉S-3블록입주자모집공고문.pdf'; Page = 5 }
)
$evidenceDir = Resolve-Path (Join-Path $PSScriptRoot '..\data\raw\evidence')
foreach ($item in $items) {
    $pdf = Join-Path $evidenceDir $item.File
    $prefix = Join-Path $outDir $item.Name
    & $poppler -f $item.Page -l $item.Page -png -r 140 $pdf $prefix | Out-Null
}
Get-ChildItem -LiteralPath $outDir -File | Select-Object FullName, Length
