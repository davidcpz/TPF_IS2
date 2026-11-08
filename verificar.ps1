# Corre los tests y todos los controles de calidad del proyecto.
# Uso: .\verificar.ps1

$fallas = 0

function Paso($nombre, [scriptblock]$comando) {
    Write-Host ""
    Write-Host "=== $nombre ===" -ForegroundColor Cyan
    & $comando
    if ($LASTEXITCODE -ne 0) {
        $script:fallas++
        Write-Host "FALLO: $nombre" -ForegroundColor Red
    } else {
        Write-Host "OK: $nombre" -ForegroundColor Green
    }
}

Paso "Tests y cobertura" { python -m pytest --cov=corporate_data_server --cov-report=term-missing }
Paso "Estilo y docstrings (ruff)" { python -m ruff check . }
Paso "Formato (black)" { python -m black --check . }
Paso "Tipos (mypy)" { python -m mypy }
Paso "Tipos (pyright)" { python -m pyright }
Paso "Seguridad (bandit)" { python -m bandit -c pyproject.toml -r src singletonclient.py observerclient.py singletonproxyobserver.py }

Write-Host ""
if ($fallas -eq 0) {
    Write-Host "Todos los controles pasaron." -ForegroundColor Green
} else {
    Write-Host "$fallas control(es) fallaron." -ForegroundColor Red
    exit 1
}
