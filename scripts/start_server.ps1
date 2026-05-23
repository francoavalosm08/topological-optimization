# Start the topology optimization web server (viewer at http://127.0.0.1:8000)
Set-Location $PSScriptRoot\..
Write-Host "Starting server at http://127.0.0.1:8000 ..."
Write-Host "Open that URL in your browser (or Cursor Simple Browser)."
python -m pip install -r requirements.txt -q
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --reload
