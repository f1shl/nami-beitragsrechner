
echo "Creating venv"
python3 -m venv .venv
.venv/bin/activate
python -m pip install --upgrade pip
echo "Installing python packages from requirements.txt"
pip install -r requirements.txt
deactivate

echo "Successfully created venv for nami-beitragsrechner"

