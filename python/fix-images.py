#!/usr/bin/env python3
"""
图片格式检测和修复工具 - Python版本
检测图片文件的真实格式，并修正文件扩展名
"""

import os
import sys
import time
import asyncio
import aiofiles
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Tuple

class ImageFormatDetector:
    """图片格式检测器"""
    
    # 文件魔法数字（文件头）
    MAGIC_NUMBERS = {
        'gif': [b'GIF87a', b'GIF89a'],
        'jpg': [b'\xff\xd8\xff'],
        'png': [b'\x89PNG\r\n\x1a\n'],
        'webp': [b'RIFF', b'WEBP'],  # WebP需要特殊处理
        'bmp': [b'BM'],
        'tiff': [b'II*\x00', b'MM\x00*'],
    }
    
    @staticmethod
    async def detect_format(file_path: str) -> Optional[str]:
        """
        检测图片文件的真实格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            真实的文件格式，如果无法识别则返回None
        """
        try:
            async with aiofiles.open(file_path, 'rb') as file:
                # 读取前20个字节，足够识别大部分图片格式
                header = await file.read(20)
                
                if len(header) < 4:
                    return None
                
                # GIF 检测
                if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
                    return 'gif'
                
                # JPEG 检测
                if header.startswith(b'\xff\xd8\xff'):
                    return 'jpg'
                
                # PNG 检测
                if header.startswith(b'\x89PNG\r\n\x1a\n'):
                    return 'png'
                
                # WebP 检测
                if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
                    return 'webp'
                
                # BMP 检测
                if header.startswith(b'BM'):
                    return 'bmp'
                
                # TIFF 检测
                if header.startswith(b'II*\x00') or header.startswith(b'MM\x00*'):
                    return 'tiff'
                
                return None
                
        except Exception as e:
            print(f"读取文件失败: {file_path} - {e}")
            return None

class ImageProcessor:
    """图片处理器"""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.detector = ImageFormatDetector()
        self.stats = {
            'processed': 0,
            'renamed': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def get_file_extension(self, file_path: str) -> str:
        """获取文件扩展名（不包含点）"""
        return Path(file_path).suffix.lower().lstrip('.')
    
    async def process_file(self, file_path: Path) -> None:
        """
        处理单个文件
        
        Args:
            file_path: 文件路径
        """
        try:
            if not file_path.is_file():
                return
            
            current_extension = self.get_file_extension(str(file_path))
            
            # 只处理常见的图片扩展名
            image_extensions = {'jpg', 'jpeg', 'gif', 'png', 'webp', 'bmp', 'tiff'}
            if current_extension not in image_extensions:
                return
            
            self.stats['processed'] += 1
            
            # 检测真实格式
            actual_format = await self.detector.detect_format(str(file_path))
            if not actual_format:
                print(f"⚠️  无法检测格式: {file_path.name}")
                self.stats['skipped'] += 1
                return
            
            # 判断是否需要重命名
            needs_rename = (
                current_extension != actual_format and 
                not (current_extension == 'jpeg' and actual_format == 'jpg')
            )
            
            if needs_rename:
                # 构造新的文件名
                new_name = file_path.stem + f'.{actual_format}'
                new_path = file_path.parent / new_name
                
                # 检查目标文件是否已存在
                if new_path.exists():
                    print(f"⚠️  目标文件已存在，跳过重命名: {file_path.name} -> {new_name}")
                    self.stats['skipped'] += 1
                    return
                
                # 重命名文件
                file_path.rename(new_path)
                print(f"✅ 已重命名: {file_path.name} -> {new_name} ({current_extension} -> {actual_format})")
                self.stats['renamed'] += 1
            else:
                print(f"✓  格式正确: {file_path.name} ({actual_format})")
                
        except Exception as e:
            print(f"❌ 处理文件失败: {file_path.name} - {e}")
            self.stats['errors'] += 1
    
    async def process_directory(self, dir_path: str) -> Dict[str, int]:
        """
        处理目录中的所有图片文件
        
        Args:
            dir_path: 目录路径
            
        Returns:
            处理统计信息
        """
        try:
            path = Path(dir_path)
            if not path.exists() or not path.is_dir():
                raise ValueError(f"目录不存在或不是有效目录: {dir_path}")
            
            # 获取所有文件
            files = [f for f in path.iterdir() if f.is_file()]
            
            # 使用信号量控制并发数
            semaphore = asyncio.Semaphore(self.max_workers)
            
            async def process_with_semaphore(file_path):
                async with semaphore:
                    await self.process_file(file_path)
            
            # 并发处理所有文件
            await asyncio.gather(*[process_with_semaphore(f) for f in files])
            
        except Exception as e:
            print(f"处理目录失败: {dir_path} - {e}")
            self.stats['errors'] += 1
        
        return self.stats

async def main():
    """主函数"""
    # 获取命令行参数
    target_dir = sys.argv[1] if len(sys.argv) > 1 else './Ori'
    
    print(f"🚀 开始处理目录: {target_dir}")
    print("正在检测和修复图片文件格式...\n")
    
    start_time = time.time()
    
    # 创建处理器并处理目录
    processor = ImageProcessor(max_workers=10)
    stats = await processor.process_directory(target_dir)
    
    end_time = time.time()
    
    # 输出统计信息
    print(f"\n{'='*50}")
    print("📋 处理完成统计:")
    print(f"   处理文件数: {stats['processed']}")
    print(f"   重命名文件数: {stats['renamed']}")
    print(f"   跳过文件数: {stats['skipped']}")
    print(f"   错误文件数: {stats['errors']}")
    print(f"   用时: {end_time - start_time:.2f}秒")
    print(f"{'='*50}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"程序执行失败: {e}")
        sys.exit(1)
