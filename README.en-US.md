

# 🃏 Joker Detector Pro - Chat Log Joker Detector

> Engineering 101 Course Project | Analyze your chat patterns with a dual-dimension approach using algorithms + AI, and quantify your "Joker Index"

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Fun%20%26%20WIP-orange.svg)

---

## 📖 Project Introduction

Are you putting too much effort into a relationship without getting a response? Are you the one who's always taking the initiative, the "joker"?

**Joker Detector Pro** is a chat log analysis tool designed for the Engineering 101 course. It can:
- 📊 Extract data from WeChat chat log Excel files
- 🧮 Quantify your "Joker Index" using a multi-dimensional algorithm
- 🤖 Perform in-depth emotional relationship analysis using AI large models
- 💌 Generate personalized emotional counseling suggestions
- 🎮 Provide a "romantic cool-down period" intervention popup

> ⚠️ This project is intended solely for course learning and entertainment purposes. Do not use it for actual relationship decision-making.

---

## ✨ Core Features

### 1. Data Parsing & Statistics
| Metric | Description |
|---------|------|
| Message Count | Counts total messages from both parties and calculates the send ratio |
| Emoji Count | Detects emojis in `[emoji]` format |
| Image Count | Detects `[图片]` markers |
| Consecutive Messages | Analyzes the maximum streak of consecutive messages sent |
| Voice/Call Logs | Detects call activity and applies a penalty coefficient |

### 2. Algorithm Evaluation System
Employs a comprehensive score based on five-dimensional ratios:

```
r1 = My messages / Their messages
r2 = My emojis / Their emojis
r3 = My max consecutive messages / Their max consecutive messages
r4 = My total words / Their total words
r5 = My images / Their images

jokernum_alg = (r1 + r2 + r3 + r4 + r5) / 5
```

### 3. Dual AI Evaluation
- **Joker Index AI**: Calls a large language model to analyze dialogue content and provides a Joker score from 0 to 1
- **Final Index** = Algorithm Score × AI Score

### 4. Emotional Personality Types (MBTI-style)

```
dim1: I/P - Proactive Initiator / Reactive Responder
dim2: E/R - Expressive / Restrained
dim3: D/S - Deep Communicator / Shallow Chatter
dim4: T/F - Persistent/Clingy / Casual/Free-spirited
```

Typical combination examples:
- 🃏 **IEDT** → 'The Devoted Performer'
- 🃏 **IRDF** → 'The Silent Guardian'
- 🃏 **PESF** → 'The Mood Setter'

### 5. Emotional Counseling AI
Generates a gentle 200-300 word emotional counseling response based on chat logs, including:
1. Emotional soothing and validation
2. Problem analysis and identification
3. 2-3 actionable suggestions

### 6. Romantic Cool-down Period Popup 🆕
When high-risk joker behavior is detected, triggers a full-screen red warning:
- Requires the user to type "I am not a joker" 5 times
- Displays an "Error" prompt for each incorrect entry
- Clears the warning upon successful completion

---

## 🚀 Quick Start

### Environment Requirements
- Python 3.8+
- pandas
- openai
- httpx
- tkinter (built-in)

### Install Dependencies

```bash
pip install pandas openai httpx
```

### Usage Steps

#### Prepare Chat Logs
1. Open the target chat on WeChat for Desktop
2. Settings → Export Chat History → Select Excel format
3. Save as `chat.xlsx`

#### Run Analysis

```bash
python final_v1.py
```

The program will prompt you with:
```
Please enter the Excel file path (e.g., chat.xlsx):
Please enter which number you are (0 or 1):
```

#### Cool-down Popup (Optional)

```bash
python jokerTset.py
```

---

## 📁 Project Structure

```
📦 project/
├── 📄 final_v1.py          # Main Program: Joker Detector Pro
├── 📄 jokerTset.py         # Cool-down Popup Module
├── 📄 README.md            # Project Documentation
└── 📄 requirements.txt     # Dependency List
```

---

## 🎯 Judgment Criteria

| jokernum Range | Verdict | Meaning |
|-------------|---------|------|
| > 2.0 | 🤡 Confirmed Joker | Severe emotional imbalance, please wake up now! |
| 1.0 ~ 2.0 | 😬 Highly Suspected Joker | Too proactive compared to the other party, risk of merely moving yourself |
| 0.5 ~ 1.0 | 😐 Mild Joker Tendencies | Occasional imbalance, but generally controllable |
| 0.2 ~ 0.5 | 🙂 Healthy Social Pattern | Relationship is basically balanced, keep it up |
| < 0.2 | 😎 Absolute Rationalist | May be the cold ruler in this relationship |

---

## ⚙️ Configuration

### AI API Configuration

Edit the configuration items in `final_v1.py`:

```python
API_KEY = "your-api-key-here"      # Enter your API Key
BASE_URL = "https://api.example.com"  # API URL
MODEL = "gpt-4"                     # Model to use
```

> 💡 If API_KEY is not configured, the program will only use algorithm evaluation and skip AI features.

---

## 🎓 Course Learning Outcomes

Through this project, we learned and practiced:

- ✅ **Data Structures**: Operations on lists, tuples, and dictionaries
- ✅ **File I/O**: Reading Excel files (pandas)
- ✅ **Network Requests**: HTTP client calls to AI APIs
- ✅ **GUI Programming**: Tkinter windows and event handling
- ✅ **Algorithm Design**: Building a multi-dimensional scoring system
- ✅ **User Experience**: Interactive CLI program design

---

## 📝 Example Output

```
============================================================
                     📊 Chat Statistics
============================================================
Xiao Ming (You) Messages: 156 | Xiao Hong (Other) Messages: 89
Xiao Ming (You) Emojis: 42 | Xiao Hong (Other) Emojis: 15
Xiao Ming (You) Images: 23 | Xiao Hong (Other) Images: 8
Xiao Ming (You) Max Consecutive: 12 | Xiao Hong (Other) Max Consecutive: 3
Xiao Ming (You) Total Words: 4521 | Xiao Hong (Other) Total Words: 1876
Voice/Call: You 2 times, Other 0 times

🧮 Algorithm Score (jokernum_alg): 1.8423
🤖 AI Score: 0.7800
🌟 Final jokernum (Algorithm × AI): 1.4370

🔍 Joker Verdict: 😬 Highly Suspected Joker — You are too proactive compared to the other party, risking merely moving yourself.

============================================================
              🃏 Your Emotional Personality Type: IEDT
============================================================
💬 Proactive Initiator | 🎨 Expressive | 📝 Deep Communicator | 🔗 Persistent/Clingy

📌 Core Issues in Emotional Investment:
  • You are the proactive initiator in conversations, holding the speaking power but prone to over-investing.
  • You love sending emojis/images, showing outward emotion.
  • You tend to write long messages, pursuing deep communication.
  • You have a tendency to persist/cling, easily ignoring the other party's boundaries.

✨ Targeted Suggestions:
  ▶ Occasionally throw the topic to the other party, observe their reaction, and avoid monologues.
  ▶ Check if they are on the same wavelength; avoid pouring warmth on ice.
  ▶ Break long texts into shorter sentences to give them space to interject.
  ▶ Instead of chasing relentlessly, try stepping back; mystery is also attractive.

🎭 Typical Profile: 'The Devoted Performer' — Showing all your love with full effort, beware of just moving yourself.

============================================================
                   💌 AI Emotional Counseling
============================================================
[AI-generated gentle counseling text...]
============================================================
```

---

## 🤝 Contributions & Feedback

Issues and Pull Requests are welcome!

---

## 📜 License

This project is for course learning and exchange only. Please contact us for removal if inappropriate.

---

<div align="center">

**Made with ❤️ for Engineering 101 Course**

*The Joker Index is for reference only; sincere communication is still needed for relationship matters*

</div>
