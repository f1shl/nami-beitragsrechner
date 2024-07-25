
echo "Creating venv"
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
echo "Installing python packages from requirements.txt"
pip install -r requirements.txt
deactivate

echo "Successfully created venv for nami-beitragsrechner"

