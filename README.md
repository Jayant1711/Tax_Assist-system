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

- **Deep Conversational Discovery**: Breaks down total income into Salary, Business, Agriculture, Capital Gains (Post-July 2024 Budget), and Rental income.
- **Intelligent User Profiling**: Dynamically adjusts questioning for Salaried employees, Business Owners, and Farmers.
- **AI Memory-Recall Assistant**: Proactively suggests often-forgotten but valid deductions (e.g., parents' medical checkups, children's tuition, specific business expenses) based on the user's profile.
- **Rule-Based Legal Authority**: All final calculations are deterministic and strictly compliant with Indian Tax Laws for FY 2024-25.
- **Explainable AI (XAI)**: Provides a clear "Compliance & Logic" layer, explaining *why* a deduction was applied or rejected, referencing specific sections like 80C, 80D, 24(a), and 112A.
- **High-Fidelity Audit Report**: Generates a professional, structured table with a complete breakdown of gains, deductions, tax percentages, and legal categories.

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

## 🧠 AI Architecture & Models

This system employs a **Hybrid AI Strategy** to balance conversational flexibility with the deterministic accuracy required for financial compliance.

### **1. NLP Entity Extraction Model**
- **Architecture**: Rule-based **Named Entity Recognition (NER)** optimized for financial linguistics.
- **Capability**: Processes natural language strings (e.g., "earning 18 LPA as a dev") to extract professional profiles and numerical financial values.
- **Logic**: Implements proximity-based mapping to link extracted values to specific tax categories (Salary, Rental, 80C, etc.).

### **2. Dynamic State Machine (DSM)**
- **Role**: Orchestrates the multi-phase tax consultation pipeline.
- **Phases**: `PROFILING` → `INCOME` → `EXPENDITURE` → `RECALL` → `FINAL`.
- **Behavior**: Enables non-linear conversation transitions based on intent detection (e.g., moving to the next phase when "nothing else" is detected).

### **3. Deterministic Rule Engine (RBE)**
- **Authority**: Acts as the "Source of Truth" for all Indian Tax Law computations.
- **Compliance**: Hardcoded logic for **Section 112A** (LTCG), **Section 111A** (STCG), and **Section 24(a)** (Standard Deduction), ensuring zero "AI hallucination" in financial results.

### **4. Recall & Suggestion Model**
- **Logic**: A profile-aware inference layer that analyzes the user's profession and income bracket to suggest often-overlooked legal deductions (e.g., child tuition fees for salaried users or depreciation for business owners).

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
