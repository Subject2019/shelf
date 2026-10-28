#!/usr/bin/env bash
# 生成小体积测试样本（各约 20–100 KB）。样本已随仓库存在时无需重跑。
set -euo pipefail
cd "$(dirname "$0")"

DURATION=12

ffmpeg -y -v error -f lavfi -i "sine=frequency=440:duration=${DURATION}" \
  -c:a libmp3lame -b:a 32k \
  -metadata title="三体" -metadata artist="刘慈欣" -metadata album="三体" \
  -metadata album_artist="刘慈欣" -metadata date="2008" -metadata language="zh-CN" \
  -metadata publisher="重庆出版社" -metadata comment="中国科幻里程碑" \
  -metadata series="地球往事" -metadata "series-part=1" \
  sample.mp3

ffmpeg -y -v error -f lavfi -i "sine=frequency=440:duration=${DURATION}" \
  -c:a aac -b:a 48k \
  -metadata title="球状闪电" -metadata artist="刘慈欣" -metadata album="球状闪电" \
  -metadata date="2004" -metadata language="zh-CN" \
  sample.m4a

cat > .chapters.txt <<'EOF'
;FFMETADATA1
[CHAPTER]
TIMEBASE=1/1000
START=0
END=6000
title=第一章 科学边界
[CHAPTER]
TIMEBASE=1/1000
START=6000
END=12000
title=第二章 台球
EOF
ffmpeg -y -v error -f lavfi -i "sine=frequency=440:duration=${DURATION}" -i .chapters.txt \
  -map 0:a -map_metadata 1 -c:a aac -b:a 48k \
  -metadata title="三体·章节版" -metadata artist="刘慈欣" \
  sample.m4b
rm -f .chapters.txt

ffmpeg -y -v error -f lavfi -i "sine=frequency=440:duration=${DURATION}" \
  -c:a flac -compression_level 8 \
  -metadata title="三体" -metadata artist="刘慈欣" -metadata album="三体" \
  -metadata series="地球往事" -metadata "series-part=1" -metadata date="2008" \
  sample.flac

ffmpeg -y -v error -f lavfi -i "sine=frequency=440:duration=${DURATION}" \
  -c:a libvorbis -q:a 2 \
  -metadata title="黑暗森林" -metadata artist="刘慈欣" -metadata date="2008" \
  sample.ogg

python3 - <<'PY'
from pathlib import Path

cue = """PERFORMER "刘慈欣"
TITLE "三体"
FILE "sample.flac" WAVE
  TRACK 01 AUDIO
    TITLE "第一章 地球往事"
    PERFORMER "刘慈欣"
    INDEX 01 00:00:00
  TRACK 02 AUDIO
    TITLE "第二章 三体文明"
    INDEX 01 00:06:00
"""
Path("sample.cue").write_text(cue, encoding="utf-8")
Path("sample_gbk.cue").write_bytes(cue.encode("gb18030"))
PY

ls -lh sample.*
