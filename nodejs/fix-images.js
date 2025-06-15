#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { promisify } = require('util');

const readFile = promisify(fs.readFile);
const rename = promisify(fs.rename);
const readdir = promisify(fs.readdir);
const stat = promisify(fs.stat);

/**
 * 检测图片文件的真实格式
 * @param {string} filePath 文件路径
 * @returns {string|null} 真实的文件格式 ('jpg', 'gif', 'png', 'webp' 等)
 */
async function detectImageFormat(filePath) {
    try {
        // 只读取文件的前20个字节，足够识别大部分图片格式
        const buffer = await readFile(filePath, { start: 0, end: 19 });
        
        // GIF 格式检测
        if (buffer[0] === 0x47 && buffer[1] === 0x49 && buffer[2] === 0x46) {
            return 'gif';
        }
        
        // JPEG 格式检测
        if (buffer[0] === 0xFF && buffer[1] === 0xD8 && buffer[2] === 0xFF) {
            return 'jpg';
        }
        
        // PNG 格式检测
        if (buffer[0] === 0x89 && buffer[1] === 0x50 && buffer[2] === 0x4E && buffer[3] === 0x47) {
            return 'png';
        }
        
        // WebP 格式检测
        if (buffer.toString('ascii', 0, 4) === 'RIFF' && buffer.toString('ascii', 8, 12) === 'WEBP') {
            return 'webp';
        }
        
        // BMP 格式检测
        if (buffer[0] === 0x42 && buffer[1] === 0x4D) {
            return 'bmp';
        }
        
        // TIFF 格式检测
        if ((buffer[0] === 0x49 && buffer[1] === 0x49 && buffer[2] === 0x2A && buffer[3] === 0x00) ||
            (buffer[0] === 0x4D && buffer[1] === 0x4D && buffer[2] === 0x00 && buffer[3] === 0x2A)) {
            return 'tiff';
        }
        
        return null;
    } catch (error) {
        console.error(`读取文件失败: ${filePath}`, error.message);
        return null;
    }
}

/**
 * 获取文件扩展名（不包含点）
 * @param {string} filePath 文件路径
 * @returns {string} 扩展名
 */
function getFileExtension(filePath) {
    return path.extname(filePath).toLowerCase().substring(1);
}

/**
 * 处理单个目录中的所有图片文件
 * @param {string} dirPath 目录路径
 * @returns {Promise<{processed: number, renamed: number, errors: number}>}
 */
async function processDirectory(dirPath) {
    const stats = { processed: 0, renamed: 0, errors: 0 };
    
    try {
        const files = await readdir(dirPath);
        
        // 并发处理文件，但限制并发数量以避免文件系统压力
        const batchSize = 10;
        for (let i = 0; i < files.length; i += batchSize) {
            const batch = files.slice(i, i + batchSize);
            await Promise.all(batch.map(async (file) => {
                const filePath = path.join(dirPath, file);
                
                try {
                    const fileStat = await stat(filePath);
                    if (!fileStat.isFile()) return;
                    
                    const currentExtension = getFileExtension(file);
                    
                    // 只处理常见的图片扩展名
                    const imageExtensions = ['jpg', 'jpeg', 'gif', 'png', 'webp', 'bmp', 'tiff'];
                    if (!imageExtensions.includes(currentExtension)) return;
                    
                    stats.processed++;
                    
                    const actualFormat = await detectImageFormat(filePath);
                    if (!actualFormat) {
                        console.warn(`无法检测格式: ${file}`);
                        return;
                    }
                    
                    // 需要重命名的情况
                    const needsRename = (currentExtension !== actualFormat) && 
                                       !(currentExtension === 'jpeg' && actualFormat === 'jpg') &&
                                       !(currentExtension === 'jpg' && actualFormat === 'jpg');
                    
                    if (needsRename) {
                        const newName = file.replace(/\.[^.]+$/, `.${actualFormat}`);
                        const newPath = path.join(dirPath, newName);
                        
                        // 检查目标文件是否已存在
                        try {
                            await stat(newPath);
                            console.warn(`目标文件已存在，跳过重命名: ${file} -> ${newName}`);
                            return;
                        } catch (error) {
                            // 目标文件不存在，可以重命名
                        }
                        
                        await rename(filePath, newPath);
                        console.log(`已重命名: ${file} -> ${newName} (${currentExtension} -> ${actualFormat})`);
                        stats.renamed++;
                    } else {
                        console.log(`格式正确: ${file} (${actualFormat})`);
                    }
                } catch (error) {
                    console.error(`处理文件失败: ${file}`, error.message);
                    stats.errors++;
                }
            }));
        }
    } catch (error) {
        console.error(`读取目录失败: ${dirPath}`, error.message);
        stats.errors++;
    }
    
    return stats;
}

/**
 * 主函数
 */
async function main() {
    const args = process.argv.slice(2);
    const targetDir = args[0] || './Ori';
    
    console.log(`开始处理目录: ${targetDir}`);
    console.log('正在检测和修复图片文件格式...\n');
    
    const startTime = Date.now();
    const stats = await processDirectory(targetDir);
    const endTime = Date.now();
    
    console.log('\n=== 处理完成 ===');
    console.log(`处理文件数: ${stats.processed}`);
    console.log(`重命名文件数: ${stats.renamed}`);
    console.log(`错误文件数: ${stats.errors}`);
    console.log(`用时: ${(endTime - startTime)}ms`);
}

// 如果直接运行此脚本
if (require.main === module) {
    main().catch(error => {
        console.error('程序执行失败:', error);
        process.exit(1);
    });
}

module.exports = { detectImageFormat, processDirectory };
