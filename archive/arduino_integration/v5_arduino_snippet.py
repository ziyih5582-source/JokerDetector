# -*- coding: utf-8 -*-
"""
归档片段：桌面版 v5.py 中已移除的 Arduino 串口联动代码（原第 538-586 行）。

保留原因：项目决定不再使用硬件联动，但保留可复原的实现参考。
这段代码不参与运行，import serial / platform / glob 也需要一并恢复。
"""

    # ====== 跨平台 Arduino 通信 ======
    @staticmethod
    def _find_arduino_port():
        """自动检测 Arduino 串口，找不到则返回环境变量 ARDUINO_PORT"""
        # 1) 环境变量优先（手动指定）
        env_port = os.getenv("ARDUINO_PORT", "").strip()
        if env_port:
            return env_port

        # 2) 自动扫描
        system = platform.system()
        if system == "Linux":
            candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        elif system == "Windows":
            # Windows: COM0–COM15
            candidates = [f"COM{i}" for i in range(16)]
        elif system == "Darwin":  # macOS
            candidates = sorted(glob.glob("/dev/tty.usbmodem*") + glob.glob("/dev/tty.usbserial*"))
        else:
            candidates = []

        for port in candidates:
            try:
                s = serial.Serial(port, 9600, timeout=1)
                s.close()
                return port
            except (OSError, serial.SerialException):
                continue
        return None

    def send_to_arduino(self, score):
        port = self._find_arduino_port()
        if port is None:
            print("⚠️ 硬件未联动: 未检测到 Arduino 串口。"
                  "请确认设备已连接，或设置环境变量 ARDUINO_PORT。")
            return
        try:
            ser = serial.Serial(port, 9600, timeout=1)
            # Arduino UNO 在串口打开时会自动复位，等待 2 秒使其就绪
            time.sleep(2)
            msg = f"{int(score)}\n"
            ser.write(msg.encode('utf-8'))
            ser.close()
            print(f"✅ 成功发送分数 {int(score)} → {port}")
        except Exception as e:
            print(f"⚠️ 硬件未联动: 串口 {port} 发送失败。原因：{e}")
    def _start_analysis(self):
        if not hasattr(self, 'selected_file'): return
        self.analyze_btn.configure(state='disabled'); self.progress.start(10)
