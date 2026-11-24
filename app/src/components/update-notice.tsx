// "A new version of Bowser is available": shown on every launch and every return to the app while the API's app.json (sydney/pipeline/
// app_release.json) lists a newer version for this platform than the one installed. Testers sideload APKs, so nothing
// else tells them. Self-contained (no app imports, own colours) on purpose: the same file is added to older versions'
// code and shipped to them as an OTA update (expo-updates is in every version).
//
// Google Play (1.0.0, 2026-11-18): the Play build (EAS channel `production`) never shows it, because Play updates the
// app itself and Play doesn't allow an app to send people to install an APK. Sideloaded builds (channel `preview`)
// keep it, and once Bowser is public on Play, app_release.json can point them at the Play listing (PLAY_URL) instead
// of an APK, with its own wording. That only upgrades in place when Play signs with the same key as the APKs
// (docs/PLAY_STORE.md).
import Constants from 'expo-constants';
import * as Updates from 'expo-updates';
import { useEffect, useState } from 'react';
import { AppState, Linking, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, useColorScheme, View } from 'react-native';

type Release = { version: string; url: string; notes?: string };
export type UpdateAction = 'shown' | 'update' | 'later';

const SEMVER = /^\d+\.\d+\.\d+$/;
/** Only Bowser's own EAS build pages, or its Google Play listing, open from here (same rule as export_api.py) */
export const PLAY_URL = 'https://play.google.com/store/apps/details?id=com.nathann2997.fuelforecast';
const SAFE_URL = /^https:\/\/expo\.dev\/accounts\/nathann97\/projects\/fuel-forecast\/builds\/[0-9a-f-]{36}$/;
const safeUrl = (u: string) => u === PLAY_URL || SAFE_URL.test(u);

/** The Google Play build: Play keeps it up to date, so it never shows this notice */
export const fromPlay = (channel: string | null | undefined) => channel === 'production';

/** a > b for x.y.z versions */
export function newer(a: string, b: string): boolean {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i++) if (pa[i] !== pb[i]) return pa[i] > pb[i];
  return false;
}

/** This platform's release from app.json, if it's newer than `installed` and well formed */
export function pendingRelease(json: unknown, os: string, installed: string | undefined): Release | null {
  const r = (json as Record<string, unknown> | null)?.[os] as Partial<Release> | null | undefined;
  if (!r || typeof r.version !== 'string' || typeof r.url !== 'string') return null;
  if (!SEMVER.test(r.version) || !safeUrl(r.url) || !installed || !SEMVER.test(installed)) return null;
  if (!newer(r.version, installed)) return null;
  const notes = typeof r.notes === 'string' && r.notes.length <= 300 ? r.notes : undefined;
  return { version: r.version, url: r.url, notes };
}

/** `releaseUrl`: where app.json is; a list is tried in order (the custom domain, then the repo's Pages address) */
export function UpdateNotice({ releaseUrl, onAction }: {
  releaseUrl: string | string[];
  onAction?: (a: UpdateAction, latest: string) => void;
}) {
  const dark = useColorScheme() === 'dark';
  const [rel, setRel] = useState<Release | null>(null);

  useEffect(() => {
    if (Platform.OS === 'web' || fromPlay(Updates.channel)) return;
    let live = true;
    let ctl: AbortController | null = null;
    let t: ReturnType<typeof setTimeout> | undefined;
    const urls = Array.isArray(releaseUrl) ? releaseUrl : [releaseUrl];
    // Asks at launch and again every time the app comes back to the front, so "Later" only lasts until the next
    // open: testers sideload APKs, and an old version can stop getting data without anything else telling them
    const check = (delay: number) => {
      clearTimeout(t);
      t = setTimeout(() => {
        ctl?.abort();
        const mine = (ctl = new AbortController());
        const stop = setTimeout(() => mine.abort(), 8000);   // a stalled connection: not mid-task minutes later
        const ask = async () => {
          for (let i = 0; i < urls.length; i++) {
            try {
              const r = await fetch(urls[i], { headers: { Accept: 'application/json' }, signal: mine.signal });
              if (r.ok) return await r.json();
            } catch (e) {
              if (i === urls.length - 1) throw e;
            }
          }
          return null;
        };
        ask()
          .then((j) => {
            const p = pendingRelease(j, Platform.OS, Constants.expoConfig?.version);
            if (!live || !p) return;
            // Already on screen: leave it be (and count it once)
            setRel((cur) => {
              if (!cur) onAction?.('shown', p.version);
              return cur ?? p;
            });
          })
          .catch(() => {})   // offline: ask on the next open
          .finally(() => clearTimeout(stop));
      }, delay);
    };
    // After the splash (hidden within about 4 s: lib/ota.ts launch check), so it doesn't race the first screen
    check(3500);
    const sub = AppState.addEventListener('change', (st) => {
      if (st === 'active') check(800);
    });
    return () => {
      live = false;
      clearTimeout(t);
      ctl?.abort();
      sub.remove();
    };
    // Set up once; releaseUrl and onAction don't change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!rel) return null;
  const c = dark
    ? { card: '#1d2023', fg: '#f4f1ea', fg2: '#c9c4ba', line: '#2e3236' }
    : { card: '#ffffff', fg: '#141618', fg2: '#44474b', line: '#e3dfd6' };
  const close = (a: UpdateAction) => {
    onAction?.(a, rel.version);
    setRel(null);
  };
  return (
    <Modal transparent animationType="fade" visible onRequestClose={() => close('later')} statusBarTranslucent navigationBarTranslucent>
      <View style={styles.backdrop}>
        <View style={[styles.card, { backgroundColor: c.card, borderColor: c.line }]} accessibilityViewIsModal>
          <Text style={[styles.title, { color: c.fg }]} accessibilityRole="header" maxFontSizeMultiplier={1.6}>
            A new version of Bowser is ready
          </Text>
          {/* Scrolls at large text sizes, and on a phone on its side (about 360 dp tall), so the buttons stay on screen */}
          <ScrollView style={{ maxHeight: 220, flexShrink: 1 }}>
            <Text style={[styles.body, { color: c.fg2 }]} maxFontSizeMultiplier={1.6}>
              {rel.notes ? `${rel.notes}\n\n` : ''}{rel.url === PLAY_URL
                ? 'Bowser is now on Google Play. Tap Update, then Update or Install in Google Play. From then on, Google Play keeps Bowser up to date. Your settings, pinned stations and fills stay as they are.'
                : 'Tap Update, then Install on the page that opens. When it’s downloaded, open the file to install it. Your settings, pinned stations and fills stay as they are.'}
            </Text>
            <Text style={[styles.version, { color: c.fg2 }]} maxFontSizeMultiplier={1.6}>
              Version {Constants.expoConfig?.version} → {rel.version}
            </Text>
          </ScrollView>
          <Pressable
            onPress={() => {
              Linking.openURL(rel.url).catch(() => {});
              close('update');
            }}
            accessibilityRole="button"
            style={({ pressed }) => [styles.primary, { opacity: pressed ? 0.8 : 1 }]}>
            <Text style={styles.primaryText} maxFontSizeMultiplier={1.6}>Update</Text>
          </Pressable>
          <Pressable onPress={() => close('later')} accessibilityRole="button" hitSlop={8} style={styles.later}>
            <Text style={[styles.laterText, { color: c.fg2 }]} maxFontSizeMultiplier={1.6}>Later</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 24 },
  // Capped and centred: on a tablet or a phone on its side it stays a dialog, clear of a side navigation bar
  card: { borderRadius: 16, borderWidth: StyleSheet.hairlineWidth, padding: 20, gap: 12, width: '100%', maxWidth: 480, maxHeight: '100%', alignSelf: 'center' },
  title: { fontSize: 19, fontWeight: '800' },
  body: { fontSize: 15, lineHeight: 21 },
  version: { fontSize: 13, marginTop: 8 },
  primary: { backgroundColor: '#ffb22e', borderRadius: 12, paddingVertical: 13, alignItems: 'center', marginTop: 4 },
  primaryText: { color: '#141618', fontSize: 16, fontWeight: '800' },
  later: { alignItems: 'center', paddingVertical: 6 },
  laterText: { fontSize: 15, fontWeight: '600' },
});
