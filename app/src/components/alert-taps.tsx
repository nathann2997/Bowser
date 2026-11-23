// A tapped notification opens what it names: a rise alert with a station opens that station's page (else Today, where
// the app already lands). Mounted once in the root layout, inside the router.
import * as Notifications from 'expo-notifications';
import { router, useRootNavigationState } from 'expo-router';
import { useEffect } from 'react';
import { Platform } from 'react-native';

import { track } from '@/lib/analytics';
import { isStationId } from '@/lib/api';
import { launchCheck } from '@/lib/ota';
import Storage from '@/lib/storage';

const LAST_TAP_KEY = 'alerts.lastTap';

/** Each tap is handled once: getLastNotificationResponseAsync returns the same response on every later launch. */
export function handleAlertTap(r: Notifications.NotificationResponse | null, go: (path: string) => void) {
  if (!r) return;
  const key = `${r.notification.request.identifier}|${r.notification.date}`;
  try {
    if (Storage.getItemSync(LAST_TAP_KEY) === key) return;
    Storage.setItemSync(LAST_TAP_KEY, key);
  } catch {
    return;   // without the record a cold start could reopen the station every launch
  }
  const data = (r.notification.request.content.data ?? {}) as { type?: unknown; stationId?: unknown };
  const type = typeof data.type === 'string' ? data.type : 'rise';
  track('notification.opened', { type });
  if (typeof data.stationId === 'string' && isStationId(data.stationId)) go(`/station/${encodeURIComponent(data.stationId)}?src=alert`);
}

export function AlertTaps() {
  const ready = !!useRootNavigationState()?.key;
  useEffect(() => {
    if (Platform.OS === 'web' || !ready) return;
    const go = (path: string) => router.push(path as never);
    // after the launch update check: if it restarts into an update, the tap is handled by the new bundle
    launchCheck().then(() => Notifications.getLastNotificationResponseAsync()).then((r) => handleAlertTap(r, go)).catch(() => {});
    const sub = Notifications.addNotificationResponseReceivedListener((r) => handleAlertTap(r, go));
    return () => sub.remove();
  }, [ready]);
  return null;
}
