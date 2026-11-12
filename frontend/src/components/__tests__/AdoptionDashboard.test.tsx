/**
 * AdoptionDashboard tests (Sprint 7 S7.1): tiles from the overview
 * payload, per-head table, calibration-gate progress, and the zero
 * state for a new user.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AdoptionDashboard from '../AdoptionDashboard';

const apiFetchMock = vi.fn();

vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}));

const OVERVIEW = {
  total_shown: 9,
  total_accepted: 2,
  acceptance_rate: 0.2222,
  accepted_rupees: 33800,
  resolved_events: 4,
  calibration_gate: { target: 30, met: false },
  per_head: [
    { head: '24b', shown: 3, accepted: 1, rejected: 0, ignored: 0,
      viewed: 2, dismissed: 0, savings_engine: 32500,
      accepted_savings: 32500 },
    { head: '80g', shown: 3, accepted: 1, rejected: 0, ignored: 0,
      viewed: 3, dismissed: 0, savings_engine: 1300, accepted_savings: 1300 },
  ],
};

function okResponse(data: unknown): Response {
  return { ok: true, status: 200, json: async () => data } as unknown as Response;
}

describe('AdoptionDashboard', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue(okResponse(OVERVIEW));
  });

  it('renders the funnel tiles and the Accepted-Rupee metric', async () => {
    render(<AdoptionDashboard />);

    expect(await screen.findByText('Adoption Dashboard')).toBeInTheDocument();
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText('₹33,800')).toBeInTheDocument();
    expect(screen.getByText(/Acceptance rate: 22\.2%/)).toBeInTheDocument();
    expect(screen.getByText(/engine-priced savings you accepted/)).toBeInTheDocument();
  });

  it('shows calibration gate progress toward the 30-event threshold', async () => {
    render(<AdoptionDashboard />);

    expect(await screen.findByText('4')).toBeInTheDocument();
    expect(screen.getByText('/30')).toBeInTheDocument();
    expect(screen.getByText(
      /resolved events needed before confidence is measured/)).toBeInTheDocument();
  });

  it('renders the per-head adoption table', async () => {
    render(<AdoptionDashboard />);

    expect(await screen.findByText(/24B/)).toBeInTheDocument();
    expect(screen.getByText(/80G/)).toBeInTheDocument();
    const row = screen.getByText(/24B/).closest('tr');
    expect(row).toHaveTextContent('3');
  });

  it('shows the empty state for a new user', async () => {
    apiFetchMock.mockResolvedValue(okResponse({
      total_shown: 0, total_accepted: 0, acceptance_rate: 0,
      accepted_rupees: 0, resolved_events: 0,
      calibration_gate: { target: 30, met: false }, per_head: [],
    }));

    render(<AdoptionDashboard />);

    expect(await screen.findByText(
      /No recommendations shown yet/)).toBeInTheDocument();
  });

  it('surfaces service errors', async () => {
    apiFetchMock.mockResolvedValue({ ok: false, status: 500 });

    render(<AdoptionDashboard />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Adoption service error/);
  });
});
