import { Linking, Pressable } from 'react-native';

import { T } from '@/components/ui';
import { useTheme } from '@/hooks/use-theme';
import { FUELCHECK_URL, NOT_GOVERNMENT_SHORT, SOURCE_LINE, SOURCE_NAME } from '@/lib/sources';

/** Under the prices (welcome, Today, Stations, a station's page): where they come from (tap opens FuelCheck) and that
 *  Bowser isn't a government app. Google Play asks for both to be easy to see (lib/sources.ts). */
export function SourceLine() {
  const c = useTheme();
  return (
    <Pressable
      onPress={() => Linking.openURL(FUELCHECK_URL).catch(() => {})}
      accessibilityRole="link"
      accessibilityLabel={SOURCE_LINE}
      accessibilityHint="Opens the NSW FuelCheck website"
      hitSlop={8}>
      <T kind="small">
        {'Prices: '}
        <T kind="small" color={c.link} style={{ fontWeight: '700' }}>{SOURCE_NAME}</T>
        {`. ${NOT_GOVERNMENT_SHORT}`}
      </T>
    </Pressable>
  );
}
