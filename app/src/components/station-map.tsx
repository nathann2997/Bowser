import { memo, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Platform, Pressable, StyleSheet, Text, useColorScheme, View } from 'react-native';
import MapView, { Marker, PROVIDER_GOOGLE, type MapStyleElement } from 'react-native-maps';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Supercluster from 'supercluster';

import { LocateIcon, MapPinIcon, PinIcon } from '@/components/icons';
import { notify, PINS_FULL } from '@/components/station-actions';
import { ADVICE_TONE, OffTag, openStation } from '@/components/station-row';
import { Badge, T } from '@/components/ui';
import { Colors, Radius, Spacing, type Palette } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { openInMaps } from '@/lib/directions';
import { offText } from '@/lib/discounts';
import { STALE_DAYS } from '@/lib/filters';
import { track } from '@/lib/analytics';
import { brandSuburb, stationName, updatedText } from '@/lib/format';
import type { Place, StationRow } from '@/lib/geo';
import {
  areaMoved, bboxOf, brandLabel, cheapestOf, inBox, lonSpanAt, padBox, priceTiers, regionFor, SYDNEY, zoomOf, type Region, type Tier,
} from '@/lib/map';
import { togglePin, usePins } from '@/lib/pins';

// The Stations tab's map view, like NSW FuelCheck: every station on screen as a price tag, loaded as you pan and zoom,
// grouped into numbered circles when zoomed out. Tags are coloured by the cheapest, middle and dearest third of the
// stations in view. The cheapest station in view is always its own, larger tag marked "Cheapest" (never inside a
// group), and a bar at the top of the map names it; a group shows the lowest price inside it. Tapping a tag opens a
// card over the bottom of the map with the price, the when-to-fill call and directions. Google Maps on Android, Apple
// Maps on iOS (no key needed there).
//
// Android draws each marker as a picture, and only reliably redraws it when the marker is added (react-native-maps'
// tracksViewChanges skips colour-only changes). So a tag whose look changes (colour, price, selection, theme) is keyed
// by that look and comes back as a new marker; the first moment after it mounts, it tracks its view so text is drawn.
//
// Privacy: the blue "you" dot is drawn from Bowser's own fix (the area), not the map SDK's location layer, so the map
// library never reads the phone's position. Google still serves the tiles for the area on screen.

type Props = {
  rows: StationRow[];              // every station for the fuel, filters applied (pinned ones left out); the map shows those in view
  pinned: StationRow[];            // pinned stations with a price, always shown
  footer?: ReactNode;              // the Map / List toggle, floating at the bottom of the map
  home: Place | null;
  live: boolean | null;            // false: the phone can't locate now, so `home` is only the last known fix
  radiusKm: number;                // the list's radius: how far the map shows when it opens
  median: number | undefined;
};

/** Clustering stops at this zoom (about a suburb across a phone screen): past it every station has its own tag */
const CLUSTER_MAX_ZOOM = 13;
/** A group marker's padding, and its "from" label's height and gap (dp): fixed, so the anchor can be worked out */
const CLUSTER_PAD = 2;
const CLUSTER_FROM_H = 18;
const CLUSTER_FROM_GAP = 2;
/** Room at the bottom of the map for the toggle; the Google logo sits above it */
const TOGGLE_ROOM = 72;

export function StationMap({ rows, pinned, footer, home, live, radiusKm, median }: Props) {
  const c = useTheme();
  const dark = useColorScheme() === 'dark';
  const insets = useSafeAreaInsets();
  const ref = useRef<MapView>(null);
  const start = useMemo(() => regionFor(home ?? SYDNEY, home ? radiusKm : 12), []);   // eslint-disable-line react-hooks/exhaustive-deps
  const [region, setRegion] = useState<Region>(start);
  const [width, setWidth] = useState(360);   // dp, for the zoom level
  const [selected, setSelected] = useState<string | null>(null);
  const [cardH, setCardH] = useState(0);

  const all = useMemo(() => [...pinned, ...rows], [pinned, rows]);
  const pinIds = useMemo(() => new Set(pinned.map((p) => p.id)), [pinned]);
  const sel = selected ? all.find((r) => r.id === selected) ?? null : null;
  if (selected && !sel) setSelected(null);   // it left the map (fuel or filter change): don't reopen if it comes back

  // What's on screen: the count uses the exact view; tags load a little past the edges so they don't pop in and out
  const box = useMemo(() => bboxOf(region), [region]);
  const inView = useMemo(() => all.filter((r) => inBox(box, r.la, r.lo)), [all, box]);
  const zoom = zoomOf(region, width);

  // Colours: thirds of the stations in view, recomputed only after a real move (a zoom of most of a level, or a pan of
  // over a third of the screen), so tags don't change colour on a nudge or when a tapped tag is centred
  const [tierRegion, setTierRegion] = useState<Region>(start);
  // The cheapest station follows every move of yours, but not the map centring a tapped tag: the station you just
  // opened as "Cheapest" shouldn't lose the label because the view shifted under it
  const [bestRegion, setBestRegion] = useState<Region>(start);
  const ownMove = useRef(false);
  const onRegion = (r: Region) => {
    setRegion(r);
    if (ownMove.current) {
      ownMove.current = false;
      return;
    }
    setBestRegion(r);
    const t = tierRegion;
    const moved =
      Math.abs(zoomOf(r, width) - zoomOf(t, width)) > 0.75 ||
      Math.abs(r.latitude - t.latitude) > t.latitudeDelta / 3 ||
      Math.abs(r.longitude - t.longitude) > t.longitudeDelta / 3;
    if (moved) setTierRegion(r);
  };
  const tierOf = useMemo(() => {
    const b = bboxOf(tierRegion);
    return priceTiers(all.filter((r) => !isOld(r) && inBox(b, r.la, r.lo)).map((r) => r.price));   // old prices don't set the colours
  }, [all, tierRegion]);

  // The cheapest fresh price in view: its own tag (left out of the groups below), and named in the bar over the map
  const best = useMemo(() => {
    const b = bboxOf(bestRegion);
    return cheapestOf(all.filter((r) => inBox(b, r.la, r.lo)), STALE_DAYS);
  }, [all, bestRegion]);
  const bestId = best?.id ?? null;
  // Once the card closes, the bar is back: catch up with whatever the centring move brought into view
  const close = () => {
    setSelected(null);
    setBestRegion(region);
  };

  const index = useMemo(() => {
    // 60 of supercluster's 512 = 30 dp at Google's zoom: only tags that would sit on top of each other merge.
    // Each group carries the lowest fresh price inside it (`min`; an old price counts as none).
    const sc = new Supercluster<{ id: string; min: number }, { min: number }>({
      radius: 60,
      maxZoom: CLUSTER_MAX_ZOOM,
      map: (p) => ({ min: p.min }),
      reduce: (acc, p) => {
        acc.min = Math.min(acc.min, p.min);
      },
    });
    sc.load(
      rows.filter((r) => r.id !== bestId).map((r) => ({
        type: 'Feature', properties: { id: r.id, min: isOld(r) ? Infinity : r.price }, geometry: { type: 'Point', coordinates: [r.lo, r.la] },
      })),
    );
    return sc;
  }, [rows, bestId]);
  const byId = useMemo(() => new Map(rows.map((r) => [r.id, r])), [rows]);
  const clusters = useMemo(() => index.getClusters(padBox(box, 0.15, 0.25), Math.floor(zoom)), [index, box, zoom]);

  const goHome = () => {
    if (home) ref.current?.animateToRegion(regionFor(home, radiusKm), 350);
  };
  // Follow the area when the radius changes or the area really moves (a new suburb, a drive), not on every GPS
  // refresh: useArea re-reads the fix on each focus, and a small jitter shouldn't pull a panned map back
  const followed = useRef({ home, radiusKm });
  useEffect(() => {
    const f = followed.current;
    if (!areaMoved(f.home, home, radiusKm) && f.radiusKm === radiusKm) return;
    followed.current = { home, radiusKm };
    goHome();
  }, [home, radiusKm]);   // eslint-disable-line react-hooks/exhaustive-deps

  // A tapped tag is centred in the map above the card, once the card has its height (the map's bottom padding follows it)
  useEffect(() => {
    if (!sel || !cardH) return;
    ownMove.current = true;
    ref.current?.animateCamera({ center: { latitude: sel.la, longitude: sel.lo } }, { duration: 250 });
    const t = setTimeout(() => (ownMove.current = false), 800);   // already centred: no move comes to clear it
    return () => clearTimeout(t);
  }, [selected, cardH]);   // eslint-disable-line react-hooks/exhaustive-deps

  const zoomInto = useCallback((id: number, la: number, lo: number) => {
    const z = Math.min(index.getClusterExpansionZoom(id), CLUSTER_MAX_ZOOM + 1) + 0.3;
    if (Platform.OS === 'android') {
      ref.current?.animateCamera({ center: { latitude: la, longitude: lo }, zoom: z }, { duration: 300 });
    } else {
      // Apple Maps cameras use altitude, not zoom: ask for the span instead, kept wide rather than tall
      const d = lonSpanAt(z, width);
      ref.current?.animateToRegion({ latitude: la, longitude: lo, latitudeDelta: d / 3, longitudeDelta: d }, 300);
    }
  }, [index, width]);

  const showBest = () => {
    if (!best) return;
    track('map.cheapest_opened');
    setSelected(best.id);
  };

  const n = inView.length;
  const iosTabs = Platform.OS === 'ios' ? insets.bottom + 50 : 0;
  const open = !!sel;

  return (
    <View style={{ flex: 1 }}>
      <View style={[styles.info, { borderBottomColor: c.line, backgroundColor: c.bg }]}>
        <T kind="small" style={{ flex: 1 }} numberOfLines={1}>
          {n ? `${n} station${n === 1 ? '' : 's'} in view` : 'No stations in view. Zoom out or change filters.'}
        </T>
        <MapLegend />
      </View>

      <View style={{ flex: 1 }} onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
        <MapView
          ref={ref}
          style={StyleSheet.absoluteFill}
          provider={Platform.OS === 'android' ? PROVIDER_GOOGLE : undefined}
          initialRegion={start}
          onRegionChangeComplete={onRegion}
          onPress={(e) => e.nativeEvent.action !== 'marker-press' && close()}
          customMapStyle={dark ? DARK_STYLE : LIGHT_STYLE}
          userInterfaceStyle={dark ? 'dark' : 'light'}
          showsPointsOfInterests={false}
          showsUserLocation={false}
          showsMyLocationButton={false}
          toolbarEnabled={false}
          moveOnMarkerPress={false}
          rotateEnabled={false}
          pitchEnabled={false}
          // The Google logo and the centre of the map sit above whatever covers the bottom: the toggle, or the card
          mapPadding={{ top: 0, right: 0, bottom: open && cardH ? cardH : TOGGLE_ROOM + iosTabs, left: 0 }}>
          {home?.gps && live !== false ? <MeMarker key={`me${c.bg}`} home={home} c={c} /> : null}
          {clusters.map((f) => {
            const [lo, la] = f.geometry.coordinates;
            if ('cluster' in f.properties && f.properties.cluster) {
              const { point_count: count, cluster_id: id, min } = f.properties;
              // No "from" when it would undercut the Cheapest tag: a group at the edge can hold a station just out of view
              const from = Number.isFinite(min) && !(best && min < best.price) ? min : null;
              const tier = from != null ? tierOf(from) : 'mid';
              // Keyed by place, not supercluster's id: the ids shift when the cheapest station changes (it leaves the
              // index), and every group would be redrawn
              return (
                <ClusterMarker key={`c${la.toFixed(5)},${lo.toFixed(5)}|${count}|${from}|${tier}|${c.bg}`} id={id} la={la} lo={lo} count={count} from={from} tier={tier} c={c} onPress={zoomInto} />
              );
            }
            const r = byId.get((f.properties as { id: string }).id);
            if (!r) return null;
            const tier = tierOf(r.price);
            const isSel = r.id === selected;
            return <PriceMarker key={`${r.id}|${tier}|${isSel}|${r.price}|${r.age}|${c.bg}`} r={r} tier={tier} selected={isSel} pinned={false} cheapest={false} c={c} onPress={setSelected} />;
          })}
          {best && !pinIds.has(best.id) ? (
            <PriceMarker key={`b${best.id}|${best.id === selected}|${best.price}|${c.bg}`} r={best} tier="low" selected={best.id === selected} pinned={false} cheapest c={c} onPress={setSelected} />
          ) : null}
          {pinned.map((r) => {
            const tier = tierOf(r.price);
            const isSel = r.id === selected;
            const isBest = r.id === bestId;
            return <PriceMarker key={`p${r.id}|${tier}|${isSel}|${isBest}|${r.price}|${r.age}|${c.bg}`} r={r} tier={tier} selected={isSel} pinned cheapest={isBest} c={c} onPress={setSelected} />;
          })}
        </MapView>

        {best && !open ? (
          <Pressable
            onPress={showBest}
            accessibilityRole="button"
            accessibilityLabel={`Cheapest in view: ${stationName(best.n)}, ${best.price.toFixed(1)} cents${best.d != null ? `, ${best.d.toFixed(1)} kilometres away` : ''}`}
            accessibilityHint="Shows it on the map"
            style={({ pressed }) => [
              styles.bestBar,
              { right: home ? Spacing.four + 48 + Spacing.two : Spacing.four, backgroundColor: c.surface, borderColor: c.line, opacity: pressed ? 0.7 : 1 },
            ]}>
            <View style={[styles.bestPrice, { backgroundColor: tierColors(c, 'low').bg }]}>
              <Text style={[styles.bestPriceText, { color: tierColors(c, 'low').fg }]}>{best.price.toFixed(1)}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.bestLabel, { color: c.muted }]} numberOfLines={1}>CHEAPEST IN VIEW</Text>
              {/* the name gives way first; the distance always shows */}
              <View style={{ flexDirection: 'row' }}>
                <Text style={[styles.bestName, { color: c.fg, flexShrink: 1 }]} numberOfLines={1}>{stationName(best.n)}</Text>
                {best.d != null ? <Text style={[styles.bestName, { color: c.fg2 }]}>{` · ${best.d.toFixed(1)} km`}</Text> : null}
              </View>
            </View>
            <Text style={{ color: c.muted, fontSize: 20, fontWeight: '700' }}>›</Text>
          </Pressable>
        ) : null}

        {home && !open ? (
          <Pressable
            onPress={goHome}
            accessibilityRole="button"
            accessibilityLabel={home.gps ? 'Centre on you' : 'Centre on your area'}
            style={({ pressed }) => [styles.roundBtn, { backgroundColor: c.surface, borderColor: c.line, opacity: pressed ? 0.7 : 1 }]}>
            <LocateIcon color={c.fg} size={22} />
          </Pressable>
        ) : null}

        {!open ? (
          <View style={[styles.bottom, { bottom: Spacing.four + iosTabs }]} pointerEvents="box-none">
            {footer}
          </View>
        ) : null}

        {sel ? (
          <StationCard
            r={sel}
            pinned={pinIds.has(sel.id)}
            cheapest={sel.id === bestId}
            median={median}
            onClose={close}
            bottom={iosTabs}
            onHeight={setCardH}
          />
        ) : null}
      </View>
    </View>
  );
}

// ---- Pieces

/** A price not updated for over STALE_DAYS: shown grey, as a check-before-you-drive */
const isOld = (r: StationRow) => r.age != null && r.age > STALE_DAYS;

/** Price text on a tier colour: white on the light theme's deep fills, dark on the dark theme's bright ones (contrast) */
const tierColors = (c: Palette, t: Tier) => {
  const on = c.bg === Colors.dark.bg ? c.onChip : '#ffffff';
  return t === 'low' ? { bg: c.cheap, fg: on } : t === 'high' ? { bg: c.dear, fg: on } : { bg: c.chip, fg: c.onChip };
};

/** True for a moment after mount, so Android draws the marker's view (text included) before it stops tracking it */
function useFirstPaint() {
  const [tracking, setTracking] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setTracking(false), 500);
    return () => clearTimeout(t);
  }, []);
  return tracking;
}

/** One station's price tag: the price on its colour, the brand below; pinned ones have a dark outline and a pin. The
 *  cheapest in view is green whatever its third, with a bigger price under the word "Cheapest" and a green outline, and
 *  sits above every tag but the selected one. */
const PriceMarker = memo(function PriceMarker({
  r, tier, selected, pinned, cheapest, c, onPress,
}: { r: StationRow; tier: Tier; selected: boolean; pinned: boolean; cheapest: boolean; c: Palette; onPress: (id: string) => void }) {
  const tracking = useFirstPaint();
  const old = isOld(r);
  const col = cheapest ? tierColors(c, 'low') : old ? { bg: c.calmBg, fg: c.calmFg } : tierColors(c, tier);
  const name = stationName(r.n);
  const edge = selected || pinned ? c.fg : cheapest ? c.cheap : c.line;
  return (
    <Marker
      coordinate={{ latitude: r.la, longitude: r.lo }}
      anchor={{ x: 0.5, y: 1 }}
      tracksViewChanges={tracking}
      zIndex={selected ? 30 : cheapest ? 25 : pinned ? 20 : old ? 9 : tier === 'low' ? 12 : tier === 'mid' ? 11 : 10}   // cheaper on top where they overlap
      onPress={() => onPress(r.id)}
      accessibilityLabel={`${name}, ${r.price.toFixed(1)} cents${old ? `, ${updatedText(r.age).toLowerCase()}` : ''}${pinned ? ', pinned' : ''}${cheapest ? ', cheapest in view' : ''}`}>
      {/* Selection is a thicker outline, not a scale: Android draws the marker at its layout size, so a scaled tag is clipped */}
      <View style={styles.tagWrap}>
        <View style={[styles.tag, { backgroundColor: c.surface, borderColor: edge, borderWidth: selected ? 3 : pinned || cheapest ? 2 : 1 }]}>
          <View style={[styles.tagPrice, { backgroundColor: col.bg }]}>
            {cheapest ? <Text style={[styles.tagBestText, { color: col.fg }]}>CHEAPEST</Text> : null}
            <Text style={[styles.tagPriceText, cheapest && styles.tagPriceBest, { color: col.fg }]}>{r.price.toFixed(1)}</Text>
          </View>
          <View style={styles.tagBrand}>
            {pinned ? <PinIcon filled color={c.fg} size={11} /> : null}
            <Text style={[styles.tagBrandText, { color: c.fg2 }]} numberOfLines={1}>{brandLabel(r.b)}</Text>
          </View>
        </View>
        <View style={[styles.tagPoint, { borderTopColor: edge }]} />
      </View>
    </Marker>
  );
});

/** A group of stations too close to show apart at this zoom: the count, in the app's primary colours (not blue, so it
 *  can't be taken for the "you" dot), and under it the lowest fresh price inside ("from 189.9") on its tier colour, so
 *  you can tell which group is worth opening. Tapping zooms in until it splits. */
const ClusterMarker = memo(function ClusterMarker({
  id, la, lo, count, from, tier, c, onPress,
}: {
  id: number; la: number; lo: number; count: number; from: number | null; tier: Tier; c: Palette;
  onPress: (id: number, la: number, lo: number) => void;
}) {
  const tracking = useFirstPaint();
  const size = count < 10 ? 36 : count < 50 ? 42 : 48;
  const col = tierColors(c, tier);
  // The circle's centre stays on the point: the label below it makes the marker taller
  const h = CLUSTER_PAD * 2 + size + (from != null ? CLUSTER_FROM_H + CLUSTER_FROM_GAP : 0);
  return (
    <Marker
      coordinate={{ latitude: la, longitude: lo }}
      anchor={{ x: 0.5, y: (CLUSTER_PAD + size / 2) / h }}
      tracksViewChanges={tracking}
      zIndex={5}
      onPress={() => onPress(id, la, lo)}
      accessibilityLabel={`${count} stations${from != null ? `, from ${from.toFixed(1)} cents` : ''}. Zoom in`}>
      <View style={styles.clusterWrap}>
        <View style={[styles.cluster, { width: size, height: size, borderRadius: size / 2, backgroundColor: c.fg, borderColor: c.bg }]}>
          <Text style={[styles.clusterText, { color: c.bg }]}>{count}</Text>
        </View>
        {from != null ? (
          <View style={[styles.clusterFrom, { backgroundColor: col.bg, borderColor: c.bg }]}>
            <Text style={[styles.clusterFromText, { color: col.fg }]}>from {from.toFixed(1)}</Text>
          </View>
        ) : null}
      </View>
    </Marker>
  );
});

/** Where you are: a small blue dot with a halo, drawn from Bowser's own fix */
function MeMarker({ home, c }: { home: Place; c: Palette }) {
  const tracking = useFirstPaint();
  return (
    <Marker coordinate={{ latitude: home.la, longitude: home.lo }} anchor={{ x: 0.5, y: 0.5 }} tracksViewChanges={tracking} zIndex={1} accessibilityLabel="You">
      <View style={styles.meRing}><View style={[styles.meDot, { backgroundColor: c.tgp }]} /></View>
    </Marker>
  );
}

/** Cheaper ● ● ● Dearer: what the tag colours mean */
export function MapLegend() {
  const c = useTheme();
  return (
    <View
      style={styles.legend}
      accessible
      accessibilityLabel="Price colours: green is the cheapest third of the stations in view, amber the middle, red the dearest third, grey a price over 7 days old">
      <Text style={[styles.legendText, { color: c.muted }]}>Cheaper</Text>
      {(['low', 'mid', 'high'] as const).map((t) => (
        <View key={t} style={[styles.legendDot, { backgroundColor: tierColors(c, t).bg }]} />
      ))}
      <Text style={[styles.legendText, { color: c.muted }]}>Dearer</Text>
      <View style={[styles.legendDot, { backgroundColor: c.calmStrong, marginLeft: 6 }]} />
      <Text style={[styles.legendText, { color: c.muted }]}>Old</Text>
    </View>
  );
}

/** The tapped station, over the bottom of the map like the app's sheets: name, price, the when-to-fill call and the
 *  7-day forecast in one line, then Directions, Pin and Details. The full forecast is on the station page. */
function StationCard({
  r, pinned, cheapest, median, onClose, bottom, onHeight,
}: { r: StationRow; pinned: boolean; cheapest: boolean; median: number | undefined; onClose: () => void; bottom: number; onHeight: (h: number) => void }) {
  const c = useTheme();
  usePins();   // re-render when this station is pinned or unpinned from the card
  const [, , code, label, , fc7] = r.adv;
  const name = stationName(r.n);
  const gap = median != null ? r.price - median : null;
  const stale = r.age != null && r.age > STALE_DAYS;
  const fcDelta = fc7 != null ? fc7 - r.pump : null;
  const pin = () => {
    if (!togglePin(r.id)) notify(PINS_FULL);
  };

  return (
    <View
      onLayout={(e) => onHeight(Math.round(e.nativeEvent.layout.height))}
      style={[styles.card, { backgroundColor: c.surface, borderColor: c.line, paddingBottom: Spacing.four + bottom }]}>
      <View style={styles.cardHead}>
        <Pressable
          onPress={() => openStation(r.id, 'map')}
          accessibilityRole="button"
          accessibilityLabel={`${name}, ${r.price.toFixed(1)} cents${r.off ? ` with your ${offText(r.off)} off` : ''}, ${label}`}
          accessibilityHint="Opens the station’s prices and forecast"
          style={{ flex: 1, gap: 2 }}>
          <T style={{ fontWeight: '700', fontSize: 16 }} color={c.fg} numberOfLines={1}>{name}</T>
          <T kind="small" numberOfLines={1} color={stale ? c.up : undefined}>
            {stale ? updatedText(r.age) : `${brandSuburb(name, r.b, r.s)}${r.d != null ? ` · ${r.d.toFixed(1)} km` : ''}${r.m ? ' · Members' : ''}`}
          </T>
        </Pressable>
        <View style={{ alignItems: 'flex-end' }}>
          <T kind="bignum">{r.price.toFixed(1)}</T>
          {gap != null ? (
            <T kind="small" color={gap < -0.05 ? c.cheap : gap > 0.05 ? c.dear : c.muted} style={{ fontWeight: '600' }}>
              {Math.abs(gap) < 0.05 ? 'at median' : `${gap < 0 ? '−' : '+'}${Math.abs(gap).toFixed(1)}c vs median`}
            </T>
          ) : null}
        </View>
        <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={12} style={styles.cardClose}>
          <T color={c.muted} style={{ fontSize: 18 }}>✕</T>
        </Pressable>
      </View>

      <View style={styles.cardChips}>
        {cheapest ? (
          <View style={[styles.cardBest, { backgroundColor: tierColors(c, 'low').bg }]}>
            <Text style={{ color: tierColors(c, 'low').fg, fontSize: 12, fontWeight: '700' }}>Cheapest in view</Text>
          </View>
        ) : null}
        <Badge tone={ADVICE_TONE[code] ?? 'calm'}>{label}</Badge>
        {r.off ? <OffTag off={r.off} /> : null}
        {fcDelta != null ? (
          <T kind="small" color={c.fg2} numberOfLines={1} style={{ flexShrink: 1 }}>
            7 days: ~{fc7!.toFixed(1)}{Math.abs(fcDelta) >= 0.5 ? ` (${fcDelta > 0 ? '+' : '−'}${Math.abs(fcDelta).toFixed(1)}c)` : ''}
          </T>
        ) : null}
      </View>

      <View style={styles.cardActions}>
        <CardButton label="Directions" onPress={() => openInMaps(r.la, r.lo, name)} c={c} primary icon={<MapPinIcon color={c.bg} size={18} />} />
        <CardButton label={pinned ? 'Unpin' : 'Pin'} onPress={pin} c={c} icon={<PinIcon filled={!pinned} color={c.fg} size={16} />} />
        <CardButton label="Details" onPress={() => openStation(r.id, 'map')} c={c} />
      </View>
    </View>
  );
}

function CardButton({ label, onPress, c, primary, icon }: { label: string; onPress: () => void; c: Palette; primary?: boolean; icon?: ReactNode }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.cardBtn,
        { flex: primary ? 1.4 : 1, backgroundColor: primary ? c.fg : c.surface, borderColor: primary ? c.fg : c.line, opacity: pressed ? 0.7 : 1 },
      ]}>
      {icon}
      <Text style={{ color: primary ? c.bg : c.fg, fontWeight: '700', fontSize: 14 }}>{label}</Text>
    </Pressable>
  );
}

// ---- Google map styles (Android). Business places are hidden so Google's own petrol-station icons don't sit under
// the price tags; the dark one follows the app's dark palette.
const LIGHT_STYLE: MapStyleElement[] = [
  { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
  { featureType: 'poi', elementType: 'labels.icon', stylers: [{ saturation: -60 }, { lightness: 20 }] },
];

const DARK_STYLE: MapStyleElement[] = [
  { elementType: 'geometry', stylers: [{ color: '#1b1e22' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#8b9197' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#121417' }] },
  { featureType: 'administrative', elementType: 'geometry', stylers: [{ color: '#2a2e33' }] },
  { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#20242a' }] },
  { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
  { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#1a2a22' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#2c3137' }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#212529' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#3a4047' }] },
  { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#a6abb0' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#262a30' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0e1a26' }] },
  { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#4e6d8c' }] },
];

const styles = StyleSheet.create({
  tagWrap: { alignItems: 'center', padding: 2 },
  tag: { borderRadius: 10, overflow: 'hidden', minWidth: 62, alignItems: 'stretch' },
  tagPrice: { paddingHorizontal: 8, paddingVertical: 3, alignItems: 'center' },
  tagPriceText: { fontSize: 15, fontWeight: '800', fontVariant: ['tabular-nums'] },
  tagBrand: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 3, paddingHorizontal: 6, paddingVertical: 2 },
  tagBrandText: { fontSize: 10, fontWeight: '700', maxWidth: 76 },
  tagPoint: {
    width: 0, height: 0, marginTop: -1,
    borderLeftWidth: 6, borderRightWidth: 6, borderTopWidth: 7, borderLeftColor: 'transparent', borderRightColor: 'transparent',
  },
  tagBestText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.6 },
  tagPriceBest: { fontSize: 18 },
  clusterWrap: { padding: CLUSTER_PAD, alignItems: 'center' },
  clusterFrom: {
    height: CLUSTER_FROM_H, marginTop: CLUSTER_FROM_GAP, paddingHorizontal: 6, borderRadius: CLUSTER_FROM_H / 2, borderWidth: 1,
    alignItems: 'center', justifyContent: 'center',
  },
  clusterFromText: { fontSize: 11, fontWeight: '800', fontVariant: ['tabular-nums'] },
  cluster: { alignItems: 'center', justifyContent: 'center', borderWidth: 2 },
  clusterText: { fontWeight: '800', fontSize: 15, fontVariant: ['tabular-nums'] },
  meRing: { width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(42,120,214,0.25)', alignItems: 'center', justifyContent: 'center' },
  meDot: { width: 12, height: 12, borderRadius: 6, borderWidth: 2, borderColor: '#ffffff' },
  info: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.three, paddingHorizontal: Spacing.four, paddingBottom: Spacing.three,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  bottom: { position: 'absolute', left: 0, right: 0, alignItems: 'center' },
  roundBtn: {
    position: 'absolute', top: Spacing.three, right: Spacing.four,
    width: 48, height: 48, borderRadius: 24, borderWidth: 1, alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 3,
  },
  // Beside the locate button, the same height
  bestBar: {
    position: 'absolute', top: Spacing.three, left: Spacing.four,
    flexDirection: 'row', alignItems: 'center', gap: Spacing.two, minHeight: 48, paddingVertical: 6, paddingLeft: 6, paddingRight: Spacing.three,
    borderRadius: Radius.card, borderWidth: 1,
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 3,
  },
  bestPrice: { borderRadius: 10, paddingHorizontal: 10, minHeight: 36, alignItems: 'center', justifyContent: 'center' },
  bestPriceText: { fontSize: 17, fontWeight: '800', fontVariant: ['tabular-nums'] },
  bestLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
  bestName: { fontSize: 14, fontWeight: '700' },
  cardBest: { borderRadius: Radius.chip, paddingVertical: 3, paddingHorizontal: 9 },
  legend: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  legendText: { fontSize: 11, fontWeight: '700' },
  legendDot: { width: 9, height: 9, borderRadius: 5 },
  // Over the bottom of the map like the app's sheets (ui.tsx Sheet); the map's bottom padding follows its height
  card: {
    position: 'absolute', left: 0, right: 0, bottom: 0,
    borderTopLeftRadius: Radius.card, borderTopRightRadius: Radius.card, borderTopWidth: StyleSheet.hairlineWidth,
    padding: Spacing.four, gap: Spacing.three,
    shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 12, shadowOffset: { width: 0, height: -2 }, elevation: 12,
  },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.three },
  cardClose: { paddingLeft: Spacing.one, paddingTop: 2 },
  cardChips: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: Spacing.two },
  cardActions: { flexDirection: 'row', gap: Spacing.two },
  cardBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderRadius: Radius.chip, minHeight: 44 },
});
