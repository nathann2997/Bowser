// Keeps the home-screen widget (Android, and iOS via ./render.ios.ts) in step with the app: mounted once from the root
// layout. A no-op on web.
import type { QueryClient, QueryKey } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Platform } from 'react-native';

import { syncAlerts } from '@/lib/alerts';
import { onPinsChange } from '@/lib/pins';
import { useSettings } from '@/lib/settings';
import type { Forecast, Stations } from '@/lib/types';

import { setWidgetDataSource } from './data';
import { compactStations } from './logic';
import { requestWidgetRefresh } from './render';

export { requestWidgetRefresh };

const isWidgetData = (k: QueryKey) => k[0] === 'forecast' || k[0] === 'stations';

/** Redraws the widget when fresh forecast/stations data arrives, when pins change, and when fuel, area or discounts change.
 *  Also keeps the rise alert (lib/alerts.ts) in step with the forecast, the fuel and the alerts switch. */
export function useWidgetSync(client: QueryClient) {
  const s = useSettings();

  useEffect(() => {
    if (Platform.OS === 'web') return;
    // A new forecast (or fuel, or the switch): in step with it, and a rise the app shows counts as seen. New stations:
    // only a pending alert's text (the cached forecast may be yesterday's)
    const run = (refreshOnly: boolean) => {
      const f = client.getQueryData<Forecast>(['forecast']);
      const st = client.getQueryData<Stations>(['stations']);
      const dataAt = client.getQueryState(['stations'])?.dataUpdatedAt || undefined;
      if (f) syncAlerts(f.live, f.asof, { inApp: true, refreshOnly, stations: st ? compactStations(st).stations : undefined, dataAt });
    };
    run(false);
    return client.getQueryCache().subscribe((e) => {
      if (e.type !== 'updated' || e.action.type !== 'success') return;
      if (e.query.queryKey[0] === 'forecast') run(false);
      else if (e.query.queryKey[0] === 'stations') run(true);
    });
  }, [client, s.fuel, s.alerts]);

  useEffect(() => {
    if (Platform.OS === 'web') return;
    // updatedAt: when the app got its data (the older file), so the widget can tell the morning's data from a later
    // run's (the pipeline republishes during the day; widget/logic.ts fromAppData). Restored-from-disk data keeps its
    // original time.
    setWidgetDataSource(() => {
      const at = (k: string) => client.getQueryState([k])?.dataUpdatedAt ?? 0;
      return {
        forecast: client.getQueryData<Forecast>(['forecast']),
        stations: client.getQueryData<Stations>(['stations']),
        updatedAt: Math.min(at('forecast'), at('stations')) || undefined,
      };
    });
    const offPins = onPinsChange(() => requestWidgetRefresh());
    const offQueries = client.getQueryCache().subscribe((e) => {
      if (e.type === 'updated' && e.action.type === 'success' && isWidgetData(e.query.queryKey)) requestWidgetRefresh();
    });
    return () => {
      offPins();
      offQueries();
      setWidgetDataSource(null);
    };
  }, [client]);

  const homeKey = s.home ? `${s.home.la},${s.home.lo}` : '';
  const offKey = JSON.stringify(s.discounts);

  // What the alert names depends on the area, radius, members, discounts, pins and tank: refresh a pending one's text
  useEffect(() => {
    if (Platform.OS === 'web') return;
    const refresh = () => {
      const f = client.getQueryData<Forecast>(['forecast']);
      const st = client.getQueryData<Stations>(['stations']);
      const dataAt = client.getQueryState(['stations'])?.dataUpdatedAt || undefined;
      if (f) syncAlerts(f.live, f.asof, { inApp: true, refreshOnly: true, stations: st ? compactStations(st).stations : undefined, dataAt });
    };
    refresh();
    const off = onPinsChange(refresh);
    return () => void off();
  }, [client, homeKey, s.radiusKm, s.members, offKey, s.tankL]);
  useEffect(() => {
    if (Platform.OS !== 'web') requestWidgetRefresh();
  }, [s.fuel, homeKey, s.radiusKm, s.members, offKey]);
}
