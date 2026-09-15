#include <Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// OLED参数
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// 引脚定义
#define SERVO_PIN 9
#define LED1 2
#define LED2 3
#define BUTTON_PIN 5

Servo myServo;
int receivedNum = 0;
bool isTriggered = false;  // 60~75分：只闪灯
bool isFullAlarm = false;  // 75分以上：闪灯+转舵机

void setup() {
  Serial.begin(9600);
  myServo.attach(SERVO_PIN);
  myServo.write(0);  // 舵机初始0度

  // OLED初始化
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    while(1);
  }
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(10, 20);
  display.print("STANDBY");
  display.display();

  pinMode(LED1, OUTPUT);
  pinMode(LED2, OUTPUT);
  pinMode(BUTTON_PIN, INPUT);  // 保持3脚模块模式
}

void loop() {
  int buttonState = digitalRead(BUTTON_PIN);

  // ======================
  // 按钮复位：按下 = HIGH 触发复位
  // ======================
  if(buttonState == HIGH) {  
    delay(50); // 消抖
    if(buttonState == HIGH) {  
      myServo.write(0);
      digitalWrite(LED1, LOW);
      digitalWrite(LED2, LOW);
      isTriggered = false;
      isFullAlarm = false;

      display.clearDisplay();
      display.setCursor(10,20);
      display.print("STOP");
      display.display();
      delay(1000);
      
      display.clearDisplay();
      display.setCursor(10,20);
      display.print("STANDBY");
      display.display();
    }
  }

  // ======================
  // 串口接收数字 (对接 Python)
  // ======================
  if(Serial.available() > 0 && !isTriggered && !isFullAlarm) {
    // 推荐使用 readStringUntil，配合 Python 传来的 '\n' 最稳定，不会粘包
    String incomingString = Serial.readStringUntil('\n');
    receivedNum = incomingString.toInt();

    // OLED显示传来的小丑指数
    display.clearDisplay();
    display.setCursor(0,20);
    display.print("SCORE:");
    display.print(receivedNum);
    display.display();

    // ————————————————————
    // 核心逻辑：0-100分段判断
    // ————————————————————
    if(receivedNum >= 60 && receivedNum <= 75) {
      isTriggered = true; // 亮灯警告
    }
    else if(receivedNum > 75) {
      isFullAlarm = true; // 亮灯 + 舵机90度
      myServo.write(90);
    }
  }

  // ======================
  // LED 循环交替闪烁
  // ======================
  if(isTriggered || isFullAlarm) {
    digitalWrite(LED1, HIGH);
    digitalWrite(LED2, LOW);
    delay(150);
    digitalWrite(LED1, LOW);
    digitalWrite(LED2, HIGH);
    delay(150);
  }
}