param(
    [Parameter(Position=0)]
    [string]$Command = "test"
)

switch ($Command) {
    "run" {
        uvicorn app.main:app --port 8000 --reload
    }
    "test" {
        python -m pytest tests -q
    }
    "lint" {
        python -m ruff check .
    }
    "format" {
        python -m ruff format .
    }
    default {
        Write-Host "Usage: ./run.ps1 [run|test|lint|format]"
    }
}
