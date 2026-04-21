> [!NOTE]
> This entire project was engineered from **11:00 PM to 11:50 PM** using AI assistance for **Blostem**.


# Tax Assist AI (India) - Deep Consultant 🇮🇳

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue?style=for-the-badge&logo=typescript&logoColor=white)
![Tax Compliance](https://img.shields.io/badge/Tax_Compliance-FY_2024--25-orange?style=for-the-badge&logo=google-keep&logoColor=white)

An advanced, AI-powered tax filing assistance system specifically designed for Indian taxpayers. This system combines the precision of a **Rule-Based Engine** with the intelligence of **Conversational AI** to provide a deep-thinking tax consultant experience.



## 🚀 Overview

Tax filing in India is complex, with two distinct regimes and numerous sections for deductions and exemptions. **Tax Assist AI** simplifies this by guiding users through a deep financial discovery process, helping them identify legitimate tax-saving opportunities they might have missed.

## ✨ Key Features

- **Deep Conversational Discovery**: Human-centric flow that breaks down complex tax queries into simple, jargon-free follow-up questions.
- **Indirect Intent Mapping**: Advanced NLP that understands professional profiles and expenditures from casual conversation (e.g., "I'm a coder" or "I pay for school fees").
- **ANFIS Rule Engine**: Employs an **Adaptive Neuro-Fuzzy Inference System** (based on Jang 1991) to evaluate tax optimization strength with fuzzy logic.
- **EE-Bat Hyperparameter Tuning**: Uses an **Enhanced Evolving Bat Algorithm** to optimize the fuzzy membership functions and intent classification weights.
- **LSTM-Inspired Context tracking**: Maintains long-term conversation state to ensure seamless transitions between discovery phases.

## 🛠️ Technology Stack

### **Frontend (Core UI)**
- **Framework**: [Next.js 16](https://nextjs.org/) (App Router Architecture)
- **Language**: [TypeScript](https://www.typescriptlang.org/) for robust type safety
- **Styling**: [Vanilla CSS](https://developer.mozilla.org/en-US/docs/Web/CSS) (Custom implementation of **Glassmorphism** and **Dark Mode**)
- **State Management**: React Hooks (`useState`, `useEffect`, `useRef`)

### **Backend (Intelligence Layer)**
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (High-performance Python API)
- **Runtime**: [Python 3.10+](https://www.python.org/)
- **Data Validation**: [Pydantic](https://docs.pydantic.dev/) for strict schema enforcement
- **Server**: [Uvicorn](https://www.uvicorn.org/) (ASGI server)

### **AI & Logic Engine**
- **NLP Strategy**: Custom **Smarter Entity Extraction** using Regex and proximity-based keyword mapping.
- **Conversation Flow**: Dynamic **State Machine** (Profiling → Income → Expenditure → Recall → Final).
- **Tax Engine**: Deterministic **Rule-Based Engine** covering Sections 80C, 80D, 80E, 80G, 24(a), 112A, and 111A.
- **Compliance Guard**: Automated validation against **Indian Income Tax Rules (FY 2024-25)**.

### **Development & Deployment**
- **Version Control**: [Git](https://git-scm.com/)
- **Package Managers**: [npm](https://www.npmjs.com/) (Frontend) and [pip](https://pip.pypa.io/) (Backend)
- **Environment**: [Node.js](https://nodejs.org/)

### **1. Semantic Intent Mapping (XGBoost Inspired)**
- **Architecture**: A multi-layered intent classifier that maps natural language features to tax categories.
- **Capability**: Recognizes indirect professions ("I write code") and expenditures ("School fees for my daughter") using a semantic proximity-based mapping.

### **2. Adaptive Neuro-Fuzzy Inference System (ANFIS)**
- **Role**: The "Brain" for rule evaluation. Based on the 1991 Jang model, it combines the learning capability of neural networks with the human-like reasoning of fuzzy logic.
- **Application**: Evaluates the "strength" of a tax profile and suggests optimizations where rules might be fuzzy or complex.

### **3. EE-Bat Optimizer**
- **Algorithm**: Enhanced Evolving Bat Algorithm (Swarm Intelligence).
- **Function**: Automatically tunes the premise and consequent parameters of the ANFIS model to ensure maximum accuracy in intent mapping and profile evaluation.

### **4. Contextual State Machine (LSTM Inspired)**
- **Logic**: Maintains long-term short-term memory of the conversation history.
- **Behavior**: Enables non-linear transitions and "forgets" or "remembers" user details dynamically based on conversational context.

## 📁 Project Structure

```text
.
├── backend/
│   ├── main.py          # FastAPI API Endpoints
│   ├── tax_engine.py    # Core Rule-Based Tax Logic (Slabs, Sections)
│   ├── nlp_engine.py    # Conversational Logic & Entity Extraction
│   └── requirements.txt
└── frontend/
    ├── src/app/         # Next.js Pages & Styling
    └── src/components/  # ChatInterface & TaxReport Components
```

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python main.py
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

## ⚖️ Disclaimer

This tool is designed for assistance and informational purposes only. It is based on publicly available Indian tax rules for FY 2024-25 and does not constitute professional tax advice.

---
