#!/bin/bash
# 北京街道故事地图 - 一键更新脚本
# 只需双击此文件，地图就会自动更新

echo "========================================"
echo "北京街道故事地图 - 一键更新"
echo "========================================"

# 获取当前目录
cd "$(dirname "$0")"

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python"
    echo "   访问 https://www.python.org/downloads/ 下载安装"
    exit 1
fi

# 检查必要的库
echo "🔍 检查必要的Python库..."
python3 -c "
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

# 运行地图生成器
echo "🗺️  正在生成地图..."
python3 beijing_streets_final.py


# 等待用户查看结果
echo ""
echo "========================================"
echo "✅ 地图更新完成！"
echo "========================================"
echo ""
echo "您现在可以："
echo "1. 打开 beijing_streets_final.html 查看更新后的地图"
echo "2. 继续编辑 beijing_streets_data.xlsx 添加更多故事"
echo "3. 再次双击此文件更新地图"
echo ""
echo "按任意键退出..."
read -n 1 -s

# 尝试自动打开HTML文件
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🌐 正在尝试在浏览器中打开地图..."
    open beijing_streets_final.html 2>/dev/null || echo "⚠️  无法自动打开，请手动打开HTML文件"
fi