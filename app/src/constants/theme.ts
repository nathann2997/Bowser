// Brand palette, shared with the dashboard (sydney/pipeline/template.html :root tokens): the logo's amber drop
// (brand) on ink (#141618). Amber marks the primary action and the current choice; ink carries text; links are
// deep amber, not blue. Decision tones: act = amber card, wait = ink card with an amber line, calm = neutral.
// See docs/DESIGN.md (2026-11-24 brand pass).
import { Platform } from 'react-native';

export const Colors = {
  light: {
    bg: '#f7f5f0', surface: '#ffffff', sunk: '#efece5', line: '#e3dfd6', fg: '#141618', fg2: '#44474b', muted: '#686b6f',
    brand: '#ffb22e', onBrand: '#141618', link: '#8a5a00',
    selBg: '#141618', selFg: '#ffffff', selLine: '#141618',
    chip: '#ffb22e', onChip: '#141618',
    retail: '#b87800', tgp: '#868a8e', cheap: '#0f7a52', dear: '#b4461a',
    band: 'rgba(255,178,46,0.22)', fan: 'rgba(255,178,46,0.26)',
    up: '#b4361b', down: '#1f6e3a', flat: '#5e6266',
    noteBg: '#fff1d4', noteFg: '#5c3c00',
    actBg: '#ffb22e', actFg: '#141618', actStrong: '#141618',
    waitBg: '#141618', waitFg: '#f4f1ea', waitStrong: '#ffb22e',
    calmBg: '#efece5', calmFg: '#33373a', calmStrong: '#7d8185',
  },
  dark: {
    bg: '#141618', surface: '#1d2023', sunk: '#191b1e', line: '#2e3236', fg: '#f4f1ea', fg2: '#c9c4ba', muted: '#9a958c',
    brand: '#ffb22e', onBrand: '#141618', link: '#ffb22e',
    selBg: '#3a2c0e', selFg: '#ffcf7a', selLine: '#ffb22e',
    chip: '#ffb22e', onChip: '#141618',
    retail: '#ffb22e', tgp: '#9a958c', cheap: '#3cc28f', dear: '#f08a5d',
    band: 'rgba(255,178,46,0.16)', fan: 'rgba(255,178,46,0.2)',
    up: '#ff8a6b', down: '#8fdc9f', flat: '#a6abb0',
    noteBg: '#2a2112', noteFg: '#ffcf7a',
    actBg: '#2a2112', actFg: '#ffcf7a', actStrong: '#ffb22e',
    waitBg: '#23272b', waitFg: '#f4f1ea', waitStrong: '#ffb22e',
    calmBg: '#1d2023', calmFg: '#c9c4ba', calmStrong: '#9a958c',
  },
} as const;

export type Palette = { [K in keyof typeof Colors.light]: string };

export const Fonts = {
  mono: Platform.select({ ios: 'Menlo', default: 'monospace' }),
};

export const Spacing = { one: 4, two: 8, three: 12, four: 16, five: 24, six: 32 } as const;

export const Radius = { card: 16, chip: 999, input: 12 } as const;
