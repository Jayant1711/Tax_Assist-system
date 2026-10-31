/**
 * SavingsGraph unit tests (Sprint 3 Objective E, design §6):
 * en-IN formatted amounts, bar widths, winner badge, effective rates.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import SavingsGraph from '../SavingsGraph';

// Clean-dividing fixture: old 300000, new 150000 over a 12L gross.
const REPORT = {
  recommendation: 'New Regime',
  savings: 150000,
  old_regime: {
    total_tax: 300000,
    gross_total_income: 1200000,
    taxable_income: 1000000,
  },
  new_regime: {
    total_tax: 150000,
    gross_total_income: 1200000,
    taxable_income: 1125000,
  },
};

describe('SavingsGraph', () => {
  it('renders en-IN formatted tax amounts (lakh/crore grouping)', () => {
    render(<SavingsGraph data={REPORT} />);

    // 300000 -> "₹3,00,000" and 150000 -> "₹1,50,000" (never 300,000).
    expect(screen.getByText('₹3,00,000')).toBeInTheDocument();
    expect(screen.getByText('₹1,50,000')).toBeInTheDocument();
    expect(screen.getByText(/₹1,50,000 in taxes/)).toBeInTheDocument();
    expect(screen.queryByText('₹300,000')).not.toBeInTheDocument();
  });

  it('scales bar widths against the larger tax (old 100%, new 50%)', () => {
    const { container } = render(<SavingsGraph data={REPORT} />);

    const oldFill = container.querySelector<HTMLElement>('.regime-bar-fill.old');
    const newFill = container.querySelector<HTMLElement>('.regime-bar-fill.new');

    expect(oldFill).not.toBeNull();
    expect(newFill).not.toBeNull();
    expect(oldFill!.style.width).toBe('100%');
    expect(newFill!.style.width).toBe('50%');
  });

  it('shows the winner badge on the recommended regime and the optimal banner', () => {
    render(<SavingsGraph data={REPORT} />);

    // New Regime is the recommendation: exactly one "★ Winner" badge.
    const badges = screen.getAllByText('★ Winner');
    expect(badges).toHaveLength(1);
    expect(screen.getByText(/New Regime is Optimal/)).toBeInTheDocument();
  });

  it('moves the winner badge to Old Regime when it is recommended', () => {
    const flipped = {
      ...REPORT,
      recommendation: 'Old Regime',
      savings: 0,
    };
    render(<SavingsGraph data={flipped} />);

    expect(screen.getAllByText('★ Winner')).toHaveLength(1);
    expect(screen.getByText(/Old Regime is Optimal/)).toBeInTheDocument();
  });

  it('renders effective rates as percentages of gross income', () => {
    render(<SavingsGraph data={REPORT} />);

    // (300000 / 1200000) * 100 = 25.0 ; (150000 / 1200000) * 100 = 12.5
    expect(screen.getByText('(25.0% eff.)')).toBeInTheDocument();
    expect(screen.getByText('(12.5% eff.)')).toBeInTheDocument();
  });

  it('renders nothing without data', () => {
    const { container } = render(<SavingsGraph data={null as unknown as object} />);
    expect(container).toBeEmptyDOMElement();
  });
});
