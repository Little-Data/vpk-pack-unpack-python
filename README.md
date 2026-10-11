# vpk-pack-unpack-python

VPK（Valve Pak）​ 是 Valve Source / Source 2 引擎使用的游戏资源打包格式，本质是一种未压缩的二进制归档容器，用来把大量小文件（材质、模型、贴图、声音、地图、粒子、脚本等）打包成少数几个文件，方便游戏快速读取，也方便玩家分发 Mod / 插件

# 使用

## vpk_unpack.py（解包）

```python
python vpk_unpack.py <archive.vpk> [-o OUTDIR] [--terminator auto|yes|no] [--list]
```

v1 / v2 头（name.vpk 与 name_dir.vpk 都行）

内嵌数据（ArchiveIndex == 0x7FFF，数据在目录之后）

外部分卷（name_000.vpk、name_001.vpk…）

目录内的 preload 字节

16 字节（无终止符）与 18 字节（0xFFFF 终止符）两种条目；--terminator auto 自动识别

--list 只列清单不提取文件

## vpk_pack.py（打包）

```python
python vpk_pack.py <SRC_DIR> <OUT.vpk> [--version 1|2] [--terminator yes|no]
```

生成引擎可直接挂载的目录 VPK：数据内嵌于目录之后（0x7FFF）、带 CRC32、无 preload

偏移按规范写为「相对目录末尾」，与官方/工坊 VPK 一致

自动按扩展名/目录分组

python 环境：3.14.6