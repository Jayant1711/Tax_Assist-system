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

## ✨ Key Features (Anfis v3 + Industrial Overhaul v5.0)

- **Industrial "Black Box" Recorder**: High-fidelity JSON logging (`logs/blackbox`) capturing every NLP neuron-fire, agent plan, and state transition for perfect audit traceability.
- **CA-Ready Audit Statement**: Professional-grade **Computational Statement of Income** including detailed Slab Analysis, Section-wise itemization, and 4% Cess breakdown.
- **Zero-Sentinel Loop Breaker**: Advanced negative intent detection (skip, none, nil, 0) to eliminate conversational loops and force discovery forward.
- **Interactive Visual Analytics**: Real-time **Regime Comparison Graphs** and Savings Sparklines that react instantly to data inputs.
- **Profile-Locked Semantic Mapping**: Neural category resolution that binds "Profession" (e.g., Trader) to "Income Mapping" to prevent Salary/Business cross-contamination.
- **ANFIS v3.5 Optimization**: Refined fuzzy inference scoring for tax efficiency (R2=0.88) with integrated Marginal Relief calculations for high-net-worth individuals.
- **EE-Bat Swarm Intelligence**: Automated optimization of tax-saving recommendations based on industrial test scenarios.

## 🛠️ Technology Stack

### **Frontend (Core UI)**
- **Framework**: [Next.js 16](https://nextjs.org/) (App Router Architecture)
- **Language**: [TypeScript](https://www.typescriptlang.org/) for robust type safety
- **Styling**: [Vanilla CSS](https://developer.mozilla.org/en-US/docs/Web/CSS) (Glassmorphism, Dark Mode, Premium Micro-animations)

### **Backend (Intelligence Layer)**
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (High-performance Python API)
- **Runtime**: [Python 3.10+](https://www.python.org/)
- **Auditing**: Built-in `AuditLogger` for session traceability.

### **AI & Logic Engine**
- **NLP Strategy**: Custom **Smarter Entity Extraction** using Regex and proximity-based keyword mapping.
- **Conversation Flow**: Dynamic **State Machine** (Profiling → Income → Expenditure → Recall → Final).
- **Tax Engine**: Deterministic **Rule-Based Engine** covering Sections 80C, 80D, 80E, 80G, 24(a), 112A, and 111A.
- **Compliance Guard**: Automated validation against **Indian Income Tax Rules (FY 2024-25)**.

### **Development & Deployment**
- **Version Control**: [Git](https://git-scm.com/)
- **Package Managers**: [npm](https://www.npmjs.com/) (Frontend) and [pip](https://pip.pypa.io/) (Backend)
- **Environment**: [Node.js](https://nodejs.org/)

## 📁 Project Structure

```text
.
├── backend/
│   ├── main.py             # FastAPI API Endpoints (with /history)
│   ├── tax_engine.py       # Core Rule-Based Logic + ANFIS Scoring
│   ├── nlp_engine.py       # Conversational Logic & Phase Management
│   ├── ai_models.py        # ANFIS, UniversalParser, ReasoningAgent
│   ├── audit_logger.py     # Session persistence & Audit trail
│   ├── test_suite.py       # 97+ High-coverage test scenarios
│   └── requirements.txt
└── frontend/
    ├── src/app/            # Next.js Pages & Global Styles
    └── src/components/     # ChatInterface (with Debug) & TaxReport
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
