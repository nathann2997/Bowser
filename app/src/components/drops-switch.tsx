// The "tell me when a pinned station gets cheap" switch (More). Turning it on asks for notification permission.
import { useState } from 'react';
import { Alert, Linking, Platform, StyleSheet, Switch, View } from 'react-native';

import { T } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { setDrops } from '@/lib/drops';
import { useSettings } from '@/lib/settings';

export function DropsSwitch() {
  const c = useTheme();
  const { drops } = useSettings();
  const [busy, setBusy] = useState(false);
  if (Platform.OS === 'web') return null;
  const onChange = async (v: boolean) => {
    setBusy(true);
    const on = await setDrops(v);
    setBusy(false);
    if (v && !on)
      Alert.alert('Notifications are off', 'Allow notifications for Bowser in Settings to hear about price drops.', [
        { text: 'Not now', style: 'cancel' },
        { text: 'Open settings', onPress: () => Linking.openSettings().catch(() => {}) },
      ]);
  };
  return (
    <View style={styles.row}>
      <View style={{ flex: 1, gap: 2 }}>
        <T color={c.fg}>Price drops at pinned stations</T>
        <T kind="small">When one is at a 30-day low or well under its usual. At most 2 alerts a week</T>
      </View>
      <Switch value={drops} disabled={busy} onValueChange={onChange} accessibilityLabel="Price drops at pinned stations" />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
});
