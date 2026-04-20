> [!NOTE]
> This entire project was engineered from **11:00 PM to 11:50 PM** using AI assistance for **Blowtem**.


# Tax Assist AI (India) - Deep Consultant 🇮🇳

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

- **Frontend**: Next.js 16 (App Router), TypeScript, Vanilla CSS.
- **Backend**: FastAPI (Python), Uvicorn.
- **Design System**: Premium Dark Mode with Glassmorphism and responsive UI.
- **NLP Engine**: Custom state-machine based NLP for high-reliability financial entity extraction.

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
