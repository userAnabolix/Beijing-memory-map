@echo off
REM 北京街道故事地图 - 一键更新脚本（Windows版）
REM 只需双击此文件，地图就会自动更新

echo ========================================
echo 北京街道故事地图 - 一键更新
echo ========================================

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python
    echo    访问 https://www.python.org/downloads/ 下载安装
    echo    安装时请勾选"Add Python to PATH"
    pause
    exit /b 1
)

REM 检查必要的库
echo 🔍 检查必要的Python库...
python -c "
try:
    import pandas
    import folium
    import openpyxl
    print('✅ 所有必要的库已安装')
except ImportError as e:
    print(f'❌ 缺少必要的库: {e}')
    print('   正在自动安装...')
    import subprocess
    import sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pandas', 'folium', 'openpyxl'])
    print('✅ 库安装完成')
"

REM 运行地图生成器
echo 🗺️  正在生成地图...
python beijing_streets_final.py

echo.
echo ========================================
echo ✅ 地图更新完成！
echo ========================================
echo.
echo 您现在可以：
echo 1. 打开 beijing_streets_final.html 查看更新后的地图
echo 2. 继续编辑 beijing_streets_data.xlsx 添加更多故事
echo 3. 再次双击此文件更新地图
echo.
echo 按任意键退出...
pause >nul

REM 尝试自动打开HTML文件
if exist "beijing_streets_final.html" (
    echo 🌐 正在尝试在浏览器中打开地图...
    start beijing_streets_final.html 2>nul || echo ⚠️  无法自动打开，请手动打开HTML文件
)