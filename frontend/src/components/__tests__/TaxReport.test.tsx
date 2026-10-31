/**
 * TaxReport unit tests (Sprint 3 Objective E, design §6).
 * Contract regression: the /calculate call must carry {session_id} ONLY
 * (ADR-013 — the client-authored session dict is gone from the wire),
 * plus KPI tiles, the 500 error banner, and fy_label rendering.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import TaxReport from '../TaxReport';

const apiFetchMock = vi.fn();

// Path is relative to THIS file (__tests__/): ../../lib/api -> src/lib/api.
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}));

const CALCULATE_RESPONSE = {
  recommendation: 'New Regime',
  savings: 62750,
  efficiency_score: 87.5,
  fy_label: 'FY 2024-25 (AY 2025-26)',
  old_regime: {
    total_tax: 252750,
    gross_total_income: 2400000,
    taxable_income: 2200000,
    total_deductions: 200000,
    income_details: [{ source: 'Salary', section: '17(1)', amount: 2400000 }],
    explanations: [{ particular: '80C Investments', reason: 'PF & ELSS', section: '80C', amount: 150000 }],
    slabs_breakdown: [{ range: '0 - 4,00,000', rate: 'Nil', income: 400000, tax: 0 }],
    savings_tips: ['80D: Health insurance premium can be claimed'],
    audit_observations: [],
    risk_level: 'Low',
  },
  new_regime: {
    total_tax: 190000,
    gross_total_income: 2400000,
    taxable_income: 2325000,
    total_deductions: 75000,
    income_details: [{ source: 'Salary', section: '17(1)', amount: 2400000 }],
    explanations: [{ particular: 'Standard Deduction', reason: 'Salaried', section: '16(ia)', amount: 75000 }],
    slabs_breakdown: [{ range: '0 - 4,00,000', rate: 'Nil', income: 400000, tax: 0 }],
    savings_tips: [],
    audit_observations: [],
    risk_level: 'Low',
  },
};

function okResponse(data: unknown): Response {
  return { ok: true, status: 200, json: async () => data } as unknown as Response;
}

function errorResponse(status: number): Response {
  return { ok: false, status, json: async () => ({ detail: 'boom' }) } as unknown as Response;
}

describe('TaxReport', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue(okResponse(CALCULATE_RESPONSE));
  });

  it('posts ONLY {session_id} to /calculate (Wave D contract regression)', async () => {
    render(<TaxReport sessionId="sess_abc123" projection={{ phase: 'FINAL', salary: 2400000 }} />);

    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1));

    expect(apiFetchMock).toHaveBeenCalledWith(
      '/calculate',
      expect.objectContaining({ method: 'POST' })
    );
    const init = apiFetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(init.body));
    // The full wire body is exactly {session_id} — no session dict, no projection.
    expect(body).toEqual({ session_id: 'sess_abc123' });
    expect(body).not.toHaveProperty('session');
  });

  it('does not fetch without a sessionId', () => {
    render(<TaxReport sessionId={null} projection={{ phase: 'PROFILING' }} />);

    expect(apiFetchMock).not.toHaveBeenCalled();
  });

  it('renders the KPI tiles from the calculation response', async () => {
    render(<TaxReport sessionId="sess_abc123" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('Recommended Strategy')).toBeInTheDocument();

    const strategyTile = screen.getByText('Recommended Strategy').closest('.metric-tile');
    expect(strategyTile).toHaveTextContent('New Regime');
    expect(strategyTile).toHaveTextContent('₹62,750');

    const taxTile = screen.getByText('Net Tax Payable (New Regime)').closest('.metric-tile');
    // en-IN formatting of the engine numbers (never 190,000).
    expect(taxTile).toHaveTextContent('₹1,90,000');

    const grossTile = screen.getByText('Gross Total Income').closest('.metric-tile');
    expect(grossTile).toHaveTextContent('₹24,00,000');
    expect(grossTile).toHaveTextContent('Total deductions: ₹75,000');

    const effTile = screen.getByText('ANFIS Efficiency Score').closest('.metric-tile');
    expect(effTile).toHaveTextContent('87.5');
  });

  it('renders fy_label from the response', async () => {
    render(<TaxReport sessionId="sess_abc123" projection={{ phase: 'FINAL' }} />);

    await waitFor(() => {
      expect(screen.getAllByText(/FY 2024-25 \(AY 2025-26\)/).length).toBeGreaterThan(0);
    });
  });

  it('shows the error banner when /calculate returns 500', async () => {
    apiFetchMock.mockResolvedValue(errorResponse(500));

    render(<TaxReport sessionId="sess_abc123" projection={{ phase: 'FINAL' }} />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Calculation Service Offline/i);
    expect(screen.queryByText('Recommended Strategy')).not.toBeInTheDocument();
  });

  it('prints the session id in the statement header', async () => {
    render(<TaxReport sessionId="sess_abc123" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText(/Session ID: sess_abc123/)).toBeInTheDocument();
  });
});
