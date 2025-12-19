param(
  [string]$Python = "python"
)

if (!(Test-Path ".venv")) {
  & $Python -m venv .venv
}

& .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m apps.desktop
