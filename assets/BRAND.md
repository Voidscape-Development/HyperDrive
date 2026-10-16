# HyperDrive brand

The mark is two forward chevrons: the "forward, forward" dash input. Sources are
[`icons/icon.svg`](icons/icon.svg) and [`icons/splash.svg`](icons/splash.svg); render
them with [`scripts/gen_icons.sh`](../scripts/gen_icons.sh).

## Colors

| Name | Hex | Use |
| --- | --- | --- |
| Ink | `#111214` | Icon tile, splash background, mark on light backgrounds |
| Off-white | `#F4F4F2` | First chevron, wordmark on dark |
| Amber | `#FFB800` | Second chevron, accent bar |
| Amber (on light) | `#F0A500` | Second chevron when the mark sits on a white or light background |
| Trail | `#26272C` | Near trailing chevron on the splash |
| Trail (far) | `#1A1B1F` | Far trailing chevron on the splash |
| Muted | `#9A9BA3` | Tagline and secondary text on Ink |

Contrast on Ink: Off-white 17:1, Amber 10.8:1, Muted 6.8:1, so all three are fine for
text. Amber on white is only 2.1:1: use it for the chevron, never for text.

## Type

Saira (SIL OFL), already in [`layout/fonts/Saira`](../layout/fonts/Saira).

- Wordmark: Saira Condensed ExtraBold Italic, all caps: `HYPERDRIVE`
- Tagline and supporting text: Saira Medium

## Mark

- Drawn on a 256 × 256 grid. The app icon tile has a corner radius of 40.
- Chevrons have sharp corners. Don't round them.
- Off-white chevron first, Amber chevron second (the leading one points forward).
- One-colour version: both chevrons in Ink on light, or in Off-white on dark.
