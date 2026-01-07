# Scientific Calculator with Graphing & History

A modern Python-based **scientific and graphing calculator desktop application** built with **Tkinter**, **NumPy**, and **Matplotlib**.
The application supports advanced mathematical operations, function plotting, calculation history, and an intuitive dark-themed graphical user interface.

---

## 📌 Features

### 🔢 Scientific Calculator
- Basic arithmetic operations
- Trigonometric functions (sin, cos, tan, sec, csc, cot)
- Logarithmic functions (ln)
- Factorial, modulus, constants (π)
- DEG / RAD angle mode support
- Auto-closing parentheses for functions
- ANS (last answer recall)
- Error handling for invalid expressions

### 📈 Graphing Calculator
- Plot mathematical functions in terms of `x`
- Customizable x-range and sample size
- Multiple graph overlays
- Zoom in/out, grid toggle, autoscale view
- Export graphs as PNG images
- Embedded Matplotlib canvas with toolbar

### 🧾 History System
- Stores recent calculations
- Scrollable history overlay
- Reuse expressions with double-click
- Works in both scientific and graphing modes

### 🎛️ User Interface
- Dark-themed modern UI
- Slide-in animated sidebar
- Non-blocking dropdown overlays for functions
- Equal-sized keypad buttons
- Keyboard and mouse input support

---

## 🛠️ Technologies Used

- **Python 3**
- **Tkinter** – GUI framework
- **NumPy** – numerical computation
- **Matplotlib** – graph plotting and visualization

---

## 📂 Project Structure

```text
ScientificCalculator/
├── backend/
│   └── engine.py          # CalculatorEngine (safe evaluation & plotting helpers)
├── frontend/
│   └── gui.py             # Main GUI application
├── assets/                # Icons / images (optional)
|   └── screenshots
|   |   └── graphing_mode.png
|   |   └── history_overlay.png
|   |   └── scientific_mode.png
|   |   └── sidebar_open.png
|   └── app_icon.png
├── requirements.txt
├── ReadMe.md
└── main.py                # Entry point (optional wrapper)
```

---
## 🚀 Installation & Usage

1️⃣ Clone the Repository
```
git clone https://github.com/Wonderment16/scientific-calculator.git
cd scientific-calculator
```

2️⃣ Install Dependencies
```
pip install -r requirements.txt
```

3️⃣ Run the Application

python frontend/gui.py

## 🧪 Sample Inputs

Scientific Mode:
> sin(45) + ln(10)

Graphing Mode:
> f(x) = sin(x)

> x-min = -10

> x-max = 10

## 👨‍💻 Author

Developed as a Python Software Development Project
for Bells University of Technology – New Horizons ICT
