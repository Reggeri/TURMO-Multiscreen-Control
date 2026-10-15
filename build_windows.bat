@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo === TURMO Control: build embedded sensor engine ===
where dotnet >nul 2>&1
if errorlevel 1 goto no_dotnet
dotnet --list-sdks
if errorlevel 1 goto bridge_failed
if not exist "sensor_bridge\SensorBridge.csproj" goto bridge_failed
if exist "sensor_bridge\publish" rmdir /s /q "sensor_bridge\publish"
dotnet publish "sensor_bridge\SensorBridge.csproj" --configuration Release --runtime win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -p:UseAppHost=true --output "sensor_bridge\publish"
if errorlevel 1 goto bridge_failed
if not exist "sensor_bridge\publish\SensorBridge.exe" goto bridge_missing
for %%F in ("sensor_bridge\publish\SensorBridge.exe") do echo Sensor engine ready: %%~zF bytes
echo === Checking Python 3.11 for WinRT compatibility ===
py -3.11 --version >nul 2>&1
if errorlevel 1 goto no_python311
echo === Installing Python requirements ===
py -3.11 -m pip install -r requirements.txt
if errorlevel 1 goto python_failed
echo === Building TURMO Control ===
py -3.11 -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --name TURMO-Control --collect-binaries imageio_ffmpeg --collect-all soundcard --collect-submodules winrt.windows.foundation --collect-submodules winrt.windows.foundation.collections --collect-submodules winrt.windows.media.control --collect-submodules winrt.windows.storage.streams --add-data "nexus26_assets;nexus26_assets" --add-data "original_themes;original_themes" --add-data "music_visualizer_assets;music_visualizer_assets" --add-data "locales.json;." --add-binary "sensor_bridge\publish\SensorBridge.exe;." app.py
if errorlevel 1 goto python_failed
if not exist "dist\TURMO-Control.exe" goto python_failed
echo SUCCESS: dist\TURMO-Control.exe
pause
exit /b 0
:no_dotnet
echo ERROR: .NET 8 SDK missing. Get it at https://dotnet.microsoft.com/download/dotnet/8.0
pause
exit /b 1
:bridge_missing
echo ERROR: dotnet publish returned success, but SensorBridge.exe was not created.
echo Files in publish directory:
dir "sensor_bridge\publish"
echo Check .NET SDK version and any publish warnings above.
pause
exit /b 1
:bridge_failed
echo ERROR: SensorBridge publish failed. See the FIRST dotnet error above.
pause
exit /b 1
:no_python311
echo ERROR: Python 3.11 x64 is required for the Windows media music feature.
echo Install Python 3.11 from https://www.python.org/downloads/ and rerun this script.
echo Your Python 3.15 installation can stay installed.
pause
exit /b 1
:python_failed
echo ERROR: Python dependencies or PyInstaller failed. Check messages above.
pause
exit /b 1
