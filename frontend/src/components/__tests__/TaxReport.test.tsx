/**
 * TaxReport unit tests (Sprint 3 Objective E, design §6).
 * Contract regression: the /calculate call must carry {session_id} ONLY
 * (ADR-013 — the client-authored session dict is gone from the wire),
 * plus KPI tiles, the 500 error banner, and fy_label rendering.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  // ── Sprint 4 Phase 4A: the Applied-vs-Ignored transparency panel ──
  const TRANSPARENCY_PROJECTION = {
    phase: 'FINAL',
    salary: 4_600_000,
    '80c': 150_000,
    '80d': 50_000,
    nps: 50_000,
  };

  it('renders the Applied-vs-Ignored panel with Sec 115BAC ignored rows', async () => {
    render(
      <TaxReport
        sessionId="sess_panel"
        projection={TRANSPARENCY_PROJECTION}
      />
    );

    expect(await screen.findByText('Your Deductions — Applied vs Ignored')).toBeInTheDocument();
    // old-regime applied rows come from the payload explanations
    expect(screen.getByText(/Old Regime — deductions apply/)).toBeInTheDocument();
    // every booked head with an amount is listed as ignored under 115BAC
    const ignored = screen.getAllByText(/not allowed under Sec 115BAC/);
    expect(ignored.length).toBeGreaterThanOrEqual(3); // 80c, 80d, nps booked
    // and the regime because-clause is present
    expect(screen.getByText(/your booked/)).toBeInTheDocument();
  });

  it('omits the panel when nothing is booked', async () => {
    render(<TaxReport sessionId="sess_empty" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('Recommended Strategy')).toBeInTheDocument();
    expect(screen.queryByText('Your Deductions — Applied vs Ignored')).not.toBeInTheDocument();
  });

  it('does not double-count the standard deduction in the statement', async () => {
    render(<TaxReport sessionId="sess_std" projection={{ phase: 'FINAL' }} />);

    // the payload's own 16(ia) explanation is the only std-ded row
    await waitFor(() => {
      const rows = screen.getAllByText(/Standard Deduction/);
      expect(rows.length).toBe(1);
    });
  });

  // ── Sprint 6 Phase 3: intelligence cards (recommendation + acceptance) ──
  const CARDS_RESPONSE = {
    ...CALCULATE_RESPONSE,
    recommendations: [
      {
        rec_id: 'rec_80c',
        head: '80c',
        delta: 150000,
        estimated_savings: 46875,
        confidence: 0.85,
        reason: 'Booked 80C is priced at ₹0 in the recommended New Regime (Sec 115BAC).',
        evidence: [
          '80C booked: ₹1,50,000 of ₹1,50,000',
          'engine-priced: a top-up of ₹46,875 saves ₹46,875 (authoritative)',
        ],
        verdict: 'RECOMMEND',
      },
      {
        rec_id: 'rec_80d',
        head: '80d',
        delta: 50000,
        estimated_savings: 0,
        confidence: 0.3,
        reason: 'Priced in both regimes — no benefit.',
        verdict: 'PRICE_ONLY',
      },
    ],
  };

  it('renders the ranked intelligence cards with confidence, savings, and reason', async () => {
    apiFetchMock.mockResolvedValue(okResponse(CARDS_RESPONSE));

    render(<TaxReport sessionId="sess_cards" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('CA Recommendations — Ranked Opportunities')).toBeInTheDocument();
    expect(screen.getByText(/Section 80C$/)).toBeInTheDocument();
    expect(screen.getByText(/confidence 85%/)).toBeInTheDocument();
    expect(screen.getByText(/est. saves ₹46,875/)).toBeInTheDocument();
    expect(screen.getByText(/Booked 80C is priced at/)).toBeInTheDocument();
    // the engine-priced evidence trail is shown, not just the verdict
    expect(screen.getByText(/engine-priced: a top-up/)).toBeInTheDocument();
    // acceptance actions only on RECOMMEND cards
    expect(screen.getByText('✓ Apply this')).toBeInTheDocument();
    expect(screen.getByText('✕ Not for me')).toBeInTheDocument();
    // the priced-no-benefit card is labelled and has no action row of its own
    expect(screen.getByText(/Section 80D — no benefit/)).toBeInTheDocument();
  });

  it('fires the viewed action once per card at FINAL (S7.2)', async () => {
    apiFetchMock.mockResolvedValue(okResponse(CARDS_RESPONSE));

    render(<TaxReport sessionId="sess_cards" projection={{ phase: 'FINAL' }} />);

    await waitFor(() => {
      const viewed = apiFetchMock.mock.calls.filter(
        ([url]) => String(url).includes('/action'),
      );
      expect(viewed.length).toBe(2); // one per card
    });
    const viewedUrls = apiFetchMock.mock.calls
      .map(([url]) => String(url))
      .filter((u) => u.includes('/action'));
    expect(viewedUrls[0]).toContain('/recommendations/rec_80c/action');
    const init = apiFetchMock.mock.calls.find(
      ([url]) => String(url).includes('/recommendations/rec_80c/action'),
    )![1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({ action: 'viewed' });
  });

  it('posts the acceptance action to the event endpoint on click', async () => {
    apiFetchMock.mockResolvedValue(okResponse(CARDS_RESPONSE));

    render(<TaxReport sessionId="sess_cards" projection={{ phase: 'FINAL' }} />);

    fireEvent.click(await screen.findByText('👍 Keep as accepted'));

    await waitFor(() => {
      const actionCalls = apiFetchMock.mock.calls.filter(
        ([url, init]) => String(url).includes('/action') &&
          JSON.parse(String((init as RequestInit).body)).action === 'accepted',
      );
      expect(actionCalls.length).toBe(1);
    });
    const [url, init] = apiFetchMock.mock.calls.find(
      ([url, init]) => String(url).includes('/recommendations/rec_80c/action') &&
        JSON.parse(String((init as RequestInit).body)).action === 'accepted',
    ) as [string, RequestInit];
    expect(url).toBe('/sessions/sess_cards/recommendations/rec_80c/action');
    expect(init.method).toBe('POST');
  });

  it('Apply re-books the headroom and re-runs the priced report (S7.3)', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/apply')) {
        return Promise.resolve(okResponse({ applied: true, head: '80c',
                                             new_value: 150000 }));
      }
      return Promise.resolve(okResponse(CARDS_RESPONSE));
    });

    render(<TaxReport sessionId="sess_cards" projection={{ phase: 'FINAL' }} />);

    fireEvent.click(await screen.findByText('✓ Apply this'));

    await waitFor(() => {
      const applyCalls = apiFetchMock.mock.calls.filter(
        ([url]) => String(url).includes('/apply'),
      );
      expect(applyCalls.length).toBe(1);
    });
    const [applyUrl, applyInit] = apiFetchMock.mock.calls.find(
      ([url]) => String(url).includes('/apply'),
    ) as [string, RequestInit];
    expect(applyUrl).toBe(
      '/sessions/sess_cards/recommendations/rec_80c/apply');
    expect(applyInit.method).toBe('POST');
    // the report re-runs /calculate after a successful apply
    await waitFor(() => {
      const calcCalls = apiFetchMock.mock.calls.filter(
        ([url]) => String(url).endsWith('/calculate'),
      );
      expect(calcCalls.length).toBeGreaterThanOrEqual(2);
    });
    expect(screen.getByText(
      /Applied — headroom booked, report re-priced below/)).toBeInTheDocument();
  });

  it('omits the intelligence cards when the payload has no recommendations', async () => {
    render(<TaxReport sessionId="sess_nocards" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('Recommended Strategy')).toBeInTheDocument();
    expect(screen.queryByText('CA Recommendations — Ranked Opportunities')).not.toBeInTheDocument();
  });

  it('hides acceptance buttons until the FINAL phase (ADR-017 shown events)', async () => {
    apiFetchMock.mockResolvedValue(okResponse(CARDS_RESPONSE));

    render(<TaxReport sessionId="sess_cards_pre" projection={{ phase: 'PROFILING' }} />);

    expect(await screen.findByText('CA Recommendations — Ranked Opportunities')).toBeInTheDocument();
    expect(screen.queryByText('✓ Apply this')).not.toBeInTheDocument();
    expect(screen.getByText(/Acceptance unlocks in the final report/)).toBeInTheDocument();
  });

  it('renders the exact per-deduction impact table (Sprint 6 Phase 5)', async () => {
    apiFetchMock.mockResolvedValue(okResponse({
      ...CALCULATE_RESPONSE,
      deduction_impact: [
        {
          head: '80c',
          entered: 150000,
          applied_in_regime: false,
          tax_reduction: 0,
          tax_reduction_other_regime: 46875,
          reason: 'Not allowed under the New Regime (Sec 115BAC) — applies in the Old Regime only',
        },
        {
          head: '24b',
          entered: 200000,
          applied_in_regime: true,
          tax_reduction: 32500,
          tax_reduction_other_regime: 0,
          reason: 'Section 24(b) — capped at ₹2,00,000 (self-occupied)',
        },
      ],
    }));

    render(<TaxReport sessionId="sess_impact" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('Per-Deduction Impact — Exact (Engine-Priced)')).toBeInTheDocument();
    expect(screen.getByText('24B')).toBeInTheDocument();
    expect(screen.getByText('₹32,500')).toBeInTheDocument();
    expect(screen.getByText('✗ 115BAC')).toBeInTheDocument();
    expect(screen.getByText(/capped at ₹2,00,000/)).toBeInTheDocument();
  });

  it('omits the impact table when the payload has no deduction_impact', async () => {
    render(<TaxReport sessionId="sess_noimpact" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('Recommended Strategy')).toBeInTheDocument();
    expect(screen.queryByText('Per-Deduction Impact — Exact (Engine-Priced)')).not.toBeInTheDocument();
  });

  it('renders CA-style savings plans when the payload carries them', async () => {
    apiFetchMock.mockResolvedValue(okResponse({
      ...CALCULATE_RESPONSE,
      ca_plans: [{
        name: 'Plan A',
        levers: ['80c'],
        savings_engine: 46875,
        steps: [{ head: '80c', delta: 150000,
                  sentence: 'Top up Section 80C (investments, Rs 1.5 lakh cap) by Rs 1,50,000 (Rs 1.5 lakh cap).' }],
      }],
    }));

    render(<TaxReport sessionId="sess_plans" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('CA-Style Savings Plans')).toBeInTheDocument();
    expect(screen.getByText('Plan A')).toBeInTheDocument();
    expect(screen.getByText(/est. saves ₹46,875/)).toBeInTheDocument();
    expect(screen.getByText(/Top up Section 80C/)).toBeInTheDocument();
  });

  it('shows an error state and no success when Apply fails (S7 QA fix)', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/apply')) {
        return Promise.resolve({ ok: false, status: 409 });
      }
      return Promise.resolve(okResponse(CARDS_RESPONSE));
    });

    render(<TaxReport sessionId="sess_cards" projection={{ phase: 'FINAL' }} />);

    fireEvent.click(await screen.findByText('✓ Apply this'));

    await waitFor(() => {
      expect(apiFetchMock.mock.calls.some(
        ([url]) => String(url).includes('/apply'))).toBe(true);
    });
    // the optimistic green confirmation must NOT appear
    expect(screen.queryByText(
      /Applied — headroom booked, report re-priced below/)).not.toBeInTheDocument();
    expect(screen.getByText(
      /Apply failed — nothing was booked/)).toBeInTheDocument();
  });

  it('Apply plan posts the lever payload and shows the applied state', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/apply_plan')) {
        return Promise.resolve(okResponse({ applied: [{ head: '80c' }] }));
      }
      return Promise.resolve(okResponse({
        ...CARDS_RESPONSE,
        ca_plans: [{
          name: 'Plan A',
          levers: ['80c'],
          savings_engine: 46875,
          steps: [{ head: '80c', delta: 150000,
                    sentence: 'Top up Section 80C by Rs 1,50,000.' }],
        }],
      }));
    });

    render(<TaxReport sessionId="sess_plan" projection={{ phase: 'FINAL' }} />);

    fireEvent.click(await screen.findByText('✓ Apply plan'));

    await waitFor(() => {
      const calls = apiFetchMock.mock.calls.filter(
        ([url]) => String(url).includes('/apply_plan'));
      expect(calls.length).toBe(1);
      const [url, init] = calls[0] as [string, RequestInit];
      expect(url).toBe('/sessions/sess_plan/apply_plan');
      expect(init.method).toBe('POST');
      expect(JSON.parse(String(init.body))).toEqual({
        levers: [{ head: '80c', delta: 150000 }],
      });
    });
    expect(screen.getByText(
      /Plan applied — headroom booked, report re-priced/)).toBeInTheDocument();
  });

  it('renders the fired-rules card from ca_notes (S7 X2)', async () => {
    apiFetchMock.mockResolvedValue(okResponse({
      ...CARDS_RESPONSE,
      ca_notes: [{ rule_id: 'R03', strength: 1.0,
                   sentence: 'Section 80C is wide open; PPF or ELSS up to the Rs 1.5 lakh cap.' }],
    }));

    render(<TaxReport sessionId="sess_notes" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText(
      'How the CA Layer Thinks — Fired Rules')).toBeInTheDocument();
    expect(screen.getByText(/R03 · 100%/)).toBeInTheDocument();
    expect(screen.getByText(/Section 80C is wide open/)).toBeInTheDocument();
  });

  it('does not re-fire viewed after the post-apply reload', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/apply')) {
        return Promise.resolve(okResponse({ applied: true, head: '80c' }));
      }
      return Promise.resolve(okResponse(CARDS_RESPONSE));
    });

    render(<TaxReport sessionId="sess_cards" projection={{ phase: 'FINAL' }} />);

    fireEvent.click(await screen.findByText('✓ Apply this'));

    await waitFor(() => {
      expect(apiFetchMock.mock.calls.filter(
        ([url]) => String(url).includes('/apply')).length).toBe(1);
    });
    await waitFor(() => {
      // calculate re-ran at least twice after the apply
      expect(apiFetchMock.mock.calls.filter(
        ([url]) => String(url).endsWith('/calculate')).length
      ).toBeGreaterThanOrEqual(2);
    });
    // viewed fired exactly once per card across the whole reload cycle
    const viewedByRec: Record<string, number> = {};
    apiFetchMock.mock.calls.forEach(([url, init]) => {
      const m = String(url).match(/recommendations\/([a-z0-9_]+)\/action/);
      if (m && JSON.parse(String((init as RequestInit).body)).action === 'viewed') {
        viewedByRec[m[1]] = (viewedByRec[m[1]] || 0) + 1;
      }
    });
    expect(Object.values(viewedByRec).every((c) => c === 1)).toBe(true);
  });

  it('omits the plans card when the payload has none', async () => {
    render(<TaxReport sessionId="sess_noplans" projection={{ phase: 'FINAL' }} />);

    expect(await screen.findByText('Recommended Strategy')).toBeInTheDocument();
    expect(screen.queryByText('CA-Style Savings Plans')).not.toBeInTheDocument();
  });
});
