@echo off
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name GiaoDienMoPhong --add-data "header.png;." --add-data "forest_background.png;." GiaoDienMoPhong.py
pause
