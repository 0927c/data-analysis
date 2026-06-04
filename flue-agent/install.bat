cd /d "d:\user\K039561\桌面\data Analysis\flue-agent"
npm install 2> "%TEMP%\npm_err.txt"
echo DONE
echo Exit code: %ERRORLEVEL%
dir node_modules\@flue >nul 2>nul && echo FLUE INSTALLED || echo FLUE NOT INSTALLED
