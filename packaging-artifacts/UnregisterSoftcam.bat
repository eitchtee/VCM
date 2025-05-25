@echo off

pushd %~dp0
set INSTALLER=softcam_installer.exe
set TARGET=_internal\softcam\softcam.dll

echo ################################################################
echo Softcam Installer (softcam_installer.exe) will uninstall Softcam
echo (softcam.dll) from your system.
echo ################################################################
echo.

%INSTALLER% unregister %TARGET%

if %ERRORLEVEL% == 0 (
  echo.
  echo Successfully done.
  echo.
) else (
  echo.
  echo The process has been canceled or failed.
  echo.
)
popd
pause
