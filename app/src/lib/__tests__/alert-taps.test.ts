// Tapping a notification: opens the station it names, once (the last response comes back on every launch)
import { beforeEach, describe, expect, it, jest } from '@jest/globals';

import { handleAlertTap } from '../../components/alert-taps';

const mockStore = new Map<string, string>();
jest.mock('@/lib/storage', () => ({
  __esModule: true,
  default: { getItemSync: (k: string) => mockStore.get(k) ?? null, setItemSync: (k: string, v: string) => void mockStore.set(k, v) },
}));
const mockTracked: unknown[] = [];
jest.mock('@/lib/analytics', () => ({ track: (...a: unknown[]) => void mockTracked.push(a) }));
jest.mock('expo-router', () => ({ router: { push: () => {} }, useRootNavigationState: () => null }));
jest.mock('expo-notifications', () => ({}));

const resp = (id: string, date: number, data: Record<string, unknown>) =>
  ({ notification: { date, request: { identifier: id, content: { data } } } }) as never;

describe('alert taps', () => {
  beforeEach(() => { mockStore.clear(); mockTracked.length = 0; });
  it('opens the station once per notification, and counts the open', () => {
    const go = jest.fn();
    handleAlertTap(resp('bowser-rise', 1, { type: 'rise', stationId: '1234' }), go);
    handleAlertTap(resp('bowser-rise', 1, { type: 'rise', stationId: '1234' }), go);   // the same response, next launch
    expect(go).toHaveBeenCalledTimes(1);
    expect(go).toHaveBeenCalledWith('/station/1234?src=alert');
    expect(mockTracked).toEqual([['notification.opened', { type: 'rise' }]]);
    handleAlertTap(resp('bowser-rise', 2, { type: 'rise', stationId: '1234' }), go);   // a later alert
    expect(go).toHaveBeenCalledTimes(2);
  });
  it('stays on Today without a valid station', () => {
    const go = jest.fn();
    handleAlertTap(resp('bowser-rise', 3, { type: 'rise', stationId: null }), go);
    handleAlertTap(resp('bowser-rise', 4, { stationId: '../x' }), go);
    handleAlertTap(null, go);
    expect(go).not.toHaveBeenCalled();
    expect(mockTracked).toHaveLength(2);
  });
});
