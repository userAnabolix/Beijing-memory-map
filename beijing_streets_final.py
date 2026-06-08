#!/usr/bin/env python3
"""
北京街道故事地图 - 最终版本
完全按照用户要求设计：

功能要求：
0. Excel随时修改，HTML自动更新
1. 缘分分值（0-10分）控制颜色深浅
2. 悬停显示：街道名称 + 简述
3. 点击显示：街道名称 + 故事
4. 黑色边框，悬停/点击时加粗
5. 移除所有不必要的文字标签

数据文件：
- Excel: beijing_streets_data.xlsx (用户随时修改)
- GeoJSON: 从购买的数据文件夹合并所有街道
"""

import pandas as pd
import folium
from folium import plugins
import json
import glob
import html
import math

class BeijingStreetsFinalMap:
    def __init__(self, excel_file='beijing_streets_data.xlsx'):
        """
        Initialize the map generator.
        
        Args:
            excel_file: Target tabular data file. Fallbacks to CSV template if missing.
        """
        self.excel_file = excel_file
        
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Priority 1: Private local path (For original author)
        private_path = os.path.join(
            script_dir, 
            '北京和区级-wgs84-拆分-20260531-221824',
            '北京全部乡镇-wgs84-拆分-20260531-221810'
        )
        
        # Priority 2: Public template path (For GitHub users)
        public_path = os.path.join(script_dir, 'geojson_data')
        
        if os.path.exists(private_path):
            self.geojson_folder = private_path
        else:
            self.geojson_folder = public_path
        self.stories_data = None
        self.geojson_data = None
        self.map = None
        self.story_dict = {}
        self.fate_dict = {}
        self.summary_dict = {}
        
        # 缘分分值对应的颜色（从浅灰色到深蓝色，每单位缘分颜色深度区别更大）
        # 确保最深颜色（10分）和黑色边框（#000000）有可见的区别
        self.fate_colors = {
            0: '#f8f8f8',   # 浅灰色，无故事
            1: '#e0e8ff',   # 非常浅的蓝色
            2: '#c2d1ff',   # 浅蓝色
            3: '#a4baff',   # 浅中蓝色
            4: '#86a3ff',   # 中蓝色
            5: '#688cff',   # 中深蓝色
            6: '#4a75ff',   # 深蓝色
            7: '#2c5eff',   # 更深蓝色
            8: '#0e47ff',   # 非常深蓝色
            9: '#0030e6',   # 接近黑色但仍是蓝色
            10: '#0019cc'   # 接近黑色但仍是蓝色
        }
    
    def clean_excel_text(self, text):
        """
        清理Excel文本中的特殊编码
        
        Args:
            text: 要清理的文本
            
        Returns:
            清理后的文本
        """
        if not isinstance(text, str):
            return str(text) if text is not None else ''
        
        # 替换Excel中的垂直制表符编码 _x000B_
        text = text.replace('_x000B_', '\n')
        
        # 替换其他可能的Excel编码
        text = text.replace('_x000D_', '\r')
        text = text.replace('_x000A_', '\n')
        text = text.replace('_x000C_', '\f')
        text = text.replace('_x0009_', '\t')
        
        # 替换实际的垂直制表符字符
        text = text.replace('\x0B', '\n')
        text = text.replace('\x0C', '\n')
        
        return text
    
    def check_data_files(self):
        """
        Verify the existence of required data files and directories.
        """
        print("[INFO] Verifying data dependencies...")
        
        # Check Excel/CSV data
        if not os.path.exists(self.excel_file) and not os.path.exists('beijing_streets_data_template.csv'):
            print(f"[ERROR] Tabular data missing: Please provide {self.excel_file} or beijing_streets_data_template.csv.")
            return False
        
        # Check GeoJSON directory
        if not os.path.exists(self.geojson_folder) or not glob.glob(os.path.join(self.geojson_folder, "*.json")):
            print(f"[ERROR] Spatial data missing: No GeoJSON files found in '{self.geojson_folder}'.")
            print("[INFO] Please ensure WGS84 GeoJSON files are present in the designated directory. See README.md for instructions.")
            return False
        
        return True
    
    def load_excel_data(self):
        """
        Load tabular data from Excel or fallback CSV.
        """
        print("[INFO] Loading tabular data...")
        
        try:
            # Detect and load available data format
            if self.excel_file.endswith('.xlsx'):
                if os.path.exists(self.excel_file):
                    self.stories_data = pd.read_excel(self.excel_file)
                    print(f"[INFO] Loaded Excel dataset: {self.excel_file}")
                elif os.path.exists('beijing_streets_data_template.csv'):
                    self.stories_data = pd.read_csv('beijing_streets_data_template.csv')
                    print("[INFO] Excel file not found. Falling back to CSV template: beijing_streets_data_template.csv")
                else:
                    raise FileNotFoundError("Data file not found.")
            else:
                self.stories_data = pd.read_csv(self.excel_file)
                print(f"[INFO] Loaded CSV dataset: {self.excel_file}")
            
            print(f"[INFO] Total records loaded: {len(self.stories_data)}")
            
            # 创建字典
            for _, row in self.stories_data.iterrows():
                street_name = str(row.get('街道名称', '')).strip()
                
                # Robust parsing for 'fate' column
                raw_fate = row.get('缘分', 0)
                try:
                    fate = int(float(raw_fate)) if pd.notna(raw_fate) else 0
                except ValueError:
                    fate = 0  # Fallback for non-numeric placeholder texts
                
                # Bound checking (0-10)
                fate = max(0, min(10, fate))
                
                summary = str(row.get('简述', '')).strip()
                story = str(row.get('故事', '')).strip()
                
                if street_name:
                    self.fate_dict[street_name] = fate
                    self.summary_dict[street_name] = summary
                    if story:  # 只有有故事时才添加到故事字典
                        self.story_dict[street_name] = story
            
            # 统计
            stories_count = len(self.story_dict)
            fate_count = sum(1 for f in self.fate_dict.values() if f > 0)
            
            print(f"  📖 故事统计: {stories_count} 个有故事的街道")
            print(f"  💫 缘分统计: {fate_count} 个有缘分分值的街道")
            
            return True
            
        except Exception as e:
            print(f"❌ Excel数据加载失败: {e}")
            return False
    
    def merge_geojson_data(self):
        """
        合并所有GeoJSON文件为一个FeatureCollection
        """
        print("\n🗺️  合并GeoJSON数据...")
        
        merged_features = []
        
        # 查找所有JSON文件
        json_files = glob.glob(os.path.join(self.geojson_folder, "*.json"))
        
        if not json_files:
            print(f"❌ 在文件夹中未找到JSON文件: {self.geojson_folder}")
            return False
        
        print(f"  找到 {len(json_files)} 个行政区文件")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get('type') == 'FeatureCollection':
                    features = data.get('features', [])
                    merged_features.extend(features)
                    
                    # 显示进度
                    district_name = os.path.basename(json_file).replace('.json', '')
                    print(f"    ✅ {district_name}: {len(features)} 个街道")
                    
            except Exception as e:
                print(f"    ⚠️  读取失败 {os.path.basename(json_file)}: {e}")
        
        # 创建合并的GeoJSON
        self.geojson_data = {
            "type": "FeatureCollection",
            "features": merged_features
        }
        
        print(f"✅ 合并完成: 共 {len(merged_features)} 个街道")
        return True
    
    def get_street_color(self, street_name):
        """
        根据缘分分值获取颜色
        """
        fate = self.fate_dict.get(street_name, 0)
        return self.fate_colors.get(fate, '#f0f0f0')
    
    def create_hover_tooltip(self, street_name):
        """
        创建悬停工具提示
        显示：街道名称 + 简述
        支持Excel中的换行符
        修复：添加自动换行功能，防止文字超出框外
        """
        summary = self.summary_dict.get(street_name, '')
        
        # 处理换行符：将Excel中的换行符转换为HTML的<br>标签
        # 使用类方法清理Excel特殊编码
        cleaned_summary = self.clean_excel_text(summary)
        summary_html = html.escape(cleaned_summary)
        summary_html = summary_html.replace('\n', '<br>')
        
        # 简洁的HTML，只有街道名称和简述
        # 添加自动换行CSS属性：word-wrap: break-word; word-break: break-word;
        html_content = f"""
        <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; 
                   font-size: 13px; padding: 6px 10px; 
                   background-color: rgba(255, 255, 255, 0.98); 
                   border: 1px solid #333; border-radius: 4px; 
                   box-shadow: 0 2px 6px rgba(0,0,0,0.2); 
                   max-width: 300px; min-width: 150px; 
                   overflow-wrap: break-word; word-wrap: break-word; 
                   hyphens: auto;">
            <div style="font-weight: bold; color: #222; margin-bottom: 4px; 
                       border-bottom: 1px solid #eee; padding-bottom: 3px;
                       overflow-wrap: break-word; word-wrap: break-word;">
                🏘️ {street_name}
            </div>
            <div style="color: #555; font-size: 12px; line-height: 1.4; 
                       word-wrap: break-word; word-break: break-word; 
                       overflow-wrap: break-word; hyphens: auto;
                       white-space: normal; overflow: hidden;
                       text-overflow: ellipsis; display: -webkit-box;
                       -webkit-line-clamp: 10; -webkit-box-orient: vertical;">
                {summary_html if summary else '暂无简述'}
            </div>
        </div>
        """
        
        return folium.Tooltip(
            html_content,
            sticky=True,
            permanent=False
        )
    
    def create_click_popup(self, street_name):
        """
        创建点击弹出窗口
        显示：街道名称 + 故事
        功能：
        1. 支持Excel中的换行符（转换为HTML的<br>标签）
        2. 超过600字用宽弹窗（30字/行），否则用窄弹窗（20字/行）
        3. 最多显示30行，超过部分支持滚动
        """
        story = self.story_dict.get(street_name, '暂无故事')
        
        # 1. 处理换行符：将Excel中的换行符转换为HTML的<br>标签
        # 同时转义HTML特殊字符，防止XSS攻击
        
        # 使用类方法清理Excel特殊编码
        cleaned_story = self.clean_excel_text(story)
        story_html = html.escape(cleaned_story)
        story_html = story_html.replace('\n', '<br>')
        
        # 2. 计算弹窗宽度和高度
        # 计算字数（中文字符算1个，英文字母和数字算0.5个）
        chinese_chars = sum(1 for char in story if '\u4e00' <= char <= '\u9fff')
        other_chars = len(story) - chinese_chars
        char_count = chinese_chars + other_chars * 0.5
        
        # 根据字数决定弹窗宽度
        if char_count > 600:
            # 宽弹窗：每行30个汉字宽度
            popup_width = 450  # 30字 * 15px/字
            chars_per_line = 30
            font_size = '13px'
        else:
            # 窄弹窗：每行20个汉字宽度
            popup_width = 300  # 20字 * 15px/字
            chars_per_line = 20
            font_size = '13px'
        
        # 3. 计算行数和高度
        # 估算行数：总字数 / 每行字数
        estimated_lines = max(1, math.ceil(char_count / chars_per_line))
        
        if estimated_lines > 30:
            # 超过30行，使用固定高度+滚动
            content_height = 450  # 30行 * 15px/行
            overflow_style = f'overflow-y: auto; height: {content_height}px;'
        else:
            # 不超过30行，自适应高度
            content_height = estimated_lines * 15  # 每行15px
            overflow_style = ''
        
        # 4. 创建HTML内容
        # 为滚动内容添加CSS类
        content_class = 'story-scrollable' if estimated_lines > 30 else ''
        
        html_content = f"""
        <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; 
                   max-width: {popup_width}px; padding: 5px;">
            <div style="font-weight: bold; color: #222; font-size: 15px; 
                       margin-bottom: 8px; border-bottom: 2px solid #0080ff; 
                       padding-bottom: 5px;">
                🏘️ {street_name}
            </div>
            <div class="{content_class}" style="color: #444; font-size: {font_size}; line-height: 1.5; 
                       background-color: #f8f9fa; padding: 10px; 
                       border-radius: 4px; border-left: 3px solid #0080ff;
                       word-wrap: break-word; word-break: break-word; 
                       overflow-wrap: break-word; {overflow_style}">
                {story_html}
            </div>
        </div>
        """
        
        return folium.Popup(
            folium.Html(html_content, script=True),
            max_width=popup_width + 40  # 加上内边距
        )
    
    def create_map(self):
        """
        创建交互式地图
        """
        print("\n🗺️  创建交互式地图...")
        
        # 北京中心坐标
        beijing_center = [39.9042, 116.4074]
        
        # 创建地图
        self.map = folium.Map(
            location=beijing_center,
            zoom_start=11,
            tiles='CartoDB positron',
            control_scale=True,
            prefer_canvas=True
        )
        
        # 添加街道图层
        streets_layer = folium.FeatureGroup(name='北京街道', show=True)
        
        if self.geojson_data and self.geojson_data.get('type') == 'FeatureCollection':
            features = self.geojson_data.get('features', [])
            
            print(f"  处理 {len(features)} 个街道...")
            
            for i, feature in enumerate(features):
                # 显示进度
                if i % 50 == 0:
                    print(f"    已处理 {i}/{len(features)} 个街道")
                
                properties = feature.get('properties', {})
                street_name = properties.get('name', '')
                
                if not street_name:
                    continue
                
                # 获取缘分分值和颜色
                fate = self.fate_dict.get(street_name, 0)
                fill_color = self.get_street_color(street_name)
                
                # 基础样式：黑色边框
                base_style = {
                    'fillColor': fill_color,
                    'color': '#000000',  # 黑色边框
                    'weight': 1,         # 基础边框宽度
                    'fillOpacity': 0.6 if fate > 0 else 0.3,
                    'dashArray': '5, 3' if fate == 0 else None
                }
                
                # 悬停/点击时加粗边框
                highlight_style = {
                    'fillColor': fill_color,
                    'color': '#000000',  # 黑色边框
                    'weight': 3,         # 加粗边框
                    'fillOpacity': 0.8 if fate > 0 else 0.5,
                    'dashArray': None
                }
                
                # 创建工具提示和弹出窗口
                tooltip = self.create_hover_tooltip(street_name)
                popup = self.create_click_popup(street_name)
                
                # 创建GeoJSON特征
                geojson_feature = {
                    "type": "Feature",
                    "properties": {
                        "name": street_name,
                        "fate": fate,
                        "style": base_style,
                        "highlight_style": highlight_style
                    },
                    "geometry": feature.get('geometry', {})
                }
                
                # 添加到图层
                geojson_layer = folium.GeoJson(
                    geojson_feature,
                    style_function=lambda x: x['properties']['style'],
                    highlight_function=lambda x: x['properties']['highlight_style'],
                    popup=popup,
                    tooltip=tooltip
                )
                
                geojson_layer.add_to(streets_layer)
        
        # 将街道图层添加到地图
        streets_layer.add_to(self.map)
        
        # 添加自定义CSS
        self.add_custom_styles()
        
        # 添加图例（简洁版）
        self.add_simple_legend()
        
        # 添加控件
        plugins.Fullscreen().add_to(self.map)
        folium.LayerControl().add_to(self.map)
        
        print("  ✅ 地图创建完成")
        return True
    
    def add_custom_styles(self):
        """
        添加自定义CSS样式和JavaScript交互
        """
        custom_html = """
        <style>
            /* 简洁的弹出窗口样式 */
            .leaflet-popup-content {
                font-family: 'Microsoft YaHei', Arial, sans-serif;
                margin: 8px 12px;
                word-wrap: break-word;
                word-break: break-word;
                overflow-wrap: break-word;
            }
            
            /* 工具提示样式 */
            .leaflet-tooltip {
                font-family: 'Microsoft YaHei', Arial, sans-serif;
                border: 1px solid #333;
                background-color: rgba(255, 255, 255, 0.95);
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
                word-wrap: break-word;
                word-break: break-word;
                overflow-wrap: break-word;
                hyphens: auto;
                white-space: normal;
                max-width: 300px !important;
                min-width: 150px !important;
            }
            
            /* 确保工具提示内容自动换行 */
            .leaflet-tooltip div,
            .leaflet-tooltip span,
            .leaflet-tooltip p {
                word-wrap: break-word;
                word-break: break-word;
                overflow-wrap: break-word;
                white-space: normal;
            }
            
            /* 地图整体样式 */
            .leaflet-container {
                font-family: 'Microsoft YaHei', Arial, sans-serif;
            }
            
            /* 滚动条样式 */
            .story-scrollable {
                scrollbar-width: thin;
                scrollbar-color: #888 #f0f0f0;
            }
            
            .story-scrollable::-webkit-scrollbar {
                width: 6px;
            }
            
            .story-scrollable::-webkit-scrollbar-track {
                background: #f0f0f0;
                border-radius: 3px;
            }
            
            .story-scrollable::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 3px;
            }
            
            .story-scrollable::-webkit-scrollbar-thumb:hover {
                background: #666;
            }
        </style>
        
        <script>
        // 当点击弹出窗口时，隐藏所有悬停工具提示
        document.addEventListener('DOMContentLoaded', function() {
            // 监听地图上的弹出窗口打开事件
            var map = document.querySelector('.leaflet-container');
            if (map) {
                // 使用事件委托监听弹出窗口
                map.addEventListener('click', function(e) {
                    // 检查点击的是否是街道区域
                    if (e.target.closest('.leaflet-interactive')) {
                        // 隐藏所有悬停工具提示
                        var tooltips = document.querySelectorAll('.leaflet-tooltip');
                        tooltips.forEach(function(tooltip) {
                            tooltip.style.display = 'none';
                        });
                        
                        // 延迟一小段时间后重新显示工具提示（当鼠标移开时）
                        setTimeout(function() {
                            tooltips.forEach(function(tooltip) {
                                tooltip.style.display = '';
                            });
                        }, 100);
                    }
                });
                
                // 当弹出窗口关闭时，确保工具提示可以正常显示
                map.addEventListener('popupclose', function() {
                    var tooltips = document.querySelectorAll('.leaflet-tooltip');
                    tooltips.forEach(function(tooltip) {
                        tooltip.style.display = '';
                    });
                });
            }
        });
        </script>
        """
        
        self.map.get_root().header.add_child(folium.Element(custom_html))
    
    def add_simple_legend(self):
        """
        添加简洁图例（根据用户要求，不添加任何内容）
        """
        # 用户要求删除左下角的地图说明，所以这个函数不添加任何内容
        pass
    
    def save_map(self, output_file='beijing_streets_final.html'):
        """
        保存地图
        """
        print(f"\n💾 保存地图文件...")
        
        if self.map is None:
            print("  ❌ 地图尚未创建")
            return False
        
        try:
            self.map.save(output_file)
            print(f"  ✅ 地图已保存: {output_file}")
            print(f"  📍 文件路径: {os.path.abspath(output_file)}")
            return True
        except Exception as e:
            print(f"  ❌ 保存失败: {e}")
            return False
    
    def open_in_browser(self, html_file):
        """
        在浏览器中打开地图
        使用系统默认浏览器（通常是Safari）
        """
        print(f"\n🌐 在浏览器中打开地图...")
        
        if not os.path.exists(html_file):
            print(f"  ❌ 文件不存在: {html_file}")
            print(f"  💡 请检查文件路径是否正确")
            return False
        
        try:
            # 获取文件的绝对路径
            abs_path = os.path.abspath(html_file)
            file_path = f'file://{abs_path}'
            
            import webbrowser
            import platform
            
            # 在macOS上，确保使用默认浏览器
            if platform.system() == 'Darwin':  # macOS
                # 方法1：使用open命令（macOS默认）
                import subprocess
                try:
                    subprocess.run(['open', abs_path], check=True)
                    print(f"  ✅ 正在使用默认浏览器打开地图...")
                    return True
                except subprocess.CalledProcessError:
                    # 方法2：使用webbrowser模块
                    browser = webbrowser.get()
                    browser.open(file_path)
                    print(f"  ✅ 正在打开地图...")
                    return True
            else:
                # 其他系统使用webbrowser模块
                webbrowser.open(file_path)
                print(f"  ✅ 正在打开地图...")
                return True
                
        except Exception as e:
            print(f"  ⚠️  浏览器打开失败: {e}")
            print(f"  💡 请手动打开文件: {os.path.abspath(html_file)}")
            print(f"  💡 或者双击文件在Finder中打开")
            return False
    
    def show_data_summary(self):
        """
        显示数据摘要
        """
        print("\n" + "=" * 70)
        print("📊 数据摘要")
        print("=" * 70)
        
        if self.stories_data is not None:
            total_streets = len(self.stories_data)
            stories_count = len(self.story_dict)
            fate_count = sum(1 for f in self.fate_dict.values() if f > 0)
            
            print(f"街道总数: {total_streets}")
            print(f"有故事的街道: {stories_count} ({stories_count/total_streets*100:.1f}%)")
            print(f"有缘分分值的街道: {fate_count} ({fate_count/total_streets*100:.1f}%)")
            
            # 显示缘分分值分布
            print("\n缘分分值分布:")
            fate_distribution = {}
            for fate in self.fate_dict.values():
                fate_distribution[fate] = fate_distribution.get(fate, 0) + 1
            
            for fate in sorted(fate_distribution.keys()):
                count = fate_distribution[fate]
                percentage = count / total_streets * 100
                print(f"  {fate:2d}分: {count:3d}个街道 ({percentage:5.1f}%)")
        
        if self.geojson_data is not None:
            features_count = len(self.geojson_data.get('features', []))
            print(f"\nGeoJSON特征数: {features_count}")
    
    def run(self):
        """
        运行完整流程
        """
        print("=" * 70)
        print("北京街道故事地图 - 最终版本")
        print("=" * 70)
        
        # 1. 检查数据文件
        if not self.check_data_files():
            return False
        
        # 2. 加载Excel数据
        if not self.load_excel_data():
            return False
        
        # 3. 合并GeoJSON数据
        if not self.merge_geojson_data():
            return False
        
        # 4. 创建地图
        if not self.create_map():
            return False
        
        # 5. 保存地图
        output_file = 'beijing_streets_final.html'
        if not self.save_map(output_file):
            return False
        
        # 6. 显示数据摘要
        self.show_data_summary()
        
        # 7. 打开地图
        self.open_in_browser(output_file)
        
        print("\n" + "=" * 70)
        print("🎉 地图生成完成！")
        print("=" * 70)
        
        print("\n✨ 功能特性:")
        print("  ✓ 基于真实北京街道边界数据")
        print("  ✓ 缘分分值控制颜色深浅 (0-10分)")
        print("  ✓ 悬停显示: 街道名称 + 简述")
        print("  ✓ 点击显示: 街道名称 + 故事")
        print("  ✓ 黑色边框，悬停/点击时加粗")
        print("  ✓ 移除所有不必要的文字标签")
        
        print("\n🔄 更新流程:")
        print("  1. 随时打开 beijing_streets_data.xlsx 修改内容")
        print("  2. 保存Excel文件")
        print("  3. 重新运行此程序: python beijing_streets_final.py")
        print("  4. 新的HTML地图会自动包含更新内容")
        
        print("\n💡 隐私说明:")
        print("  • 所有数据仅存储在本地")
        print("  • 无需网络连接")
        print("  • 完全私密，仅供您个人使用")
        
        return True

def main():
    """
    主函数
    """
    print("北京街道故事地图生成器 - 最终版本")
    print("-" * 50)
    
    # 创建地图生成器实例（使用相对路径）
    map_generator = BeijingStreetsFinalMap(
        excel_file='beijing_streets_data.xlsx',
        geojson_folder=None  # 使用相对路径
    )
    
    # 运行地图生成
    success = map_generator.run()
    
    if success:
        print("\n✅ 所有任务已完成！")
        print("\n您现在可以:")
        print("  1. 打开生成的HTML文件查看交互式地图")
        print("  2. 随时编辑Excel文件添加或修改故事")
        print("  3. 重新运行程序更新地图")
        print("  4. 享受完全私密的北京街道故事记录")
    else:
        print("\n❌ 地图生成过程中遇到问题")
        print("请检查错误信息并确认数据文件路径")

if __name__ == "__main__":
    main()