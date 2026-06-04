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
bool isTriggered = false;  // 45~59：只闪灯（疑似小丑）
bool isFullAlarm = false;  // 60以上：闪灯+转舵机（确诊小丑）

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

  pinMode(LED1, OUTPUT);
  pinMode(LED2, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
}

void loop() {
  int buttonState = digitalRead(BUTTON_PIN);

  // ======================
  // 按钮复位：全部停止
  // ======================
  if(buttonState == LOW) {
    delay(50);
    if(buttonState == LOW) {
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
    }
  }

  // ======================
  // 串口接收数字
  // ======================
  if(Serial.available() > 0 && !isTriggered && !isFullAlarm) {
    receivedNum = Serial.parseInt();
    Serial.print("NUM: ");
    Serial.println(receivedNum);

    // OLED显示数值
    display.clearDisplay();
    display.setCursor(10,20);
    display.print("NUM:");
    display.print(receivedNum);
    display.display();

    // ————————————————————
    // 核心逻辑：分段判断
    // ————————————————————
    if(receivedNum >= 45 && receivedNum < 60) {
      // 45~59：只亮灯，不转舵机（疑似小丑）
      isTriggered = true;
    }
    else if(receivedNum >= 60) {
      // 60以上：亮灯 + 舵机90度（确诊小丑）
      isFullAlarm = true;
      myServo.write(90);
    }
  }

  // ======================
  // LED 循环交替闪烁
  // 45~59 或 60以上 都会闪
  // ======================
  if(isTriggered || isFullAlarm) {
    digitalWrite(LED1, HIGH);
    digitalWrite(LED2, LOW);
    delay(200);
    digitalWrite(LED1, LOW);
    digitalWrite(LED2, HIGH);
    delay(200);
  }
}
