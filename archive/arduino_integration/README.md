# Arduino 硬件联动 · 归档

项目决定不再使用硬件联动，Arduino 相关内容全部集中到本目录与 `archive/v5_arduino/`，**没有删除**，随时可以复原。

## 归档内容

| 位置 | 内容 |
| --- | --- |
| `archive/v5_arduino/v5_arduino.ino` | 原 `v5_arduino/` 固件（接收分数并驱动灯光/报警） |
| `archive/arduino_old/arduino_old.ino` | 更早一版固件（原本就在 archive 内） |
| `archive/arduino_integration/v5_arduino_snippet.py` | 从 `v5.py` 中移除的串口通信代码片段 |

## 从活动代码中移除了什么

`v5.py`（桌面版）：

- `import serial` / `import glob` / `import platform` / `import time`（它们只被串口代码使用）
- `_find_arduino_port()`：跨平台串口自动探测（`ARDUINO_PORT` 环境变量、`/dev/ttyACM*`、`COM*`、`/dev/tty.usbmodem*`）
- `send_to_arduino(score)`：分析完成后把分数写入串口
- `_display_result()` 中的 `self.send_to_arduino(...)` 调用
- 窗口副标题由「智能情感分析与 Arduino 硬件联动终端」改为「智能情感分析终端」

`.env.example` 中的 `ARDUINO_PORT` 变量、`README.md` 的项目结构与依赖说明中的 `pyserial` / `v5_arduino` 也已同步移除。

Web 版（`web/`）从未包含串口代码，无需改动。

## 如何复原

1. 把 `v5_arduino_snippet.py` 中的方法块贴回 `v5.py` 的 `JokerDetectorApp` 类中（`_export_report` 之后、`_start_analysis` 之前）。
2. 在 `_display_result()` 里恢复调用：
   ```python
   r = self.result; is_joker, joker_type, stats = r['is_joker'], r['joker_type'], r['stats']
   self.send_to_arduino(stats['jokernum_alg'])
   ```
3. 恢复 `import serial, glob, platform, time`，并 `pip install pyserial`。
4. 固件仍可用：把 `archive/v5_arduino/v5_arduino.ino` 烧录到 Arduino UNO（波特率 9600）。
