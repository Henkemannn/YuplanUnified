import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

function contrastRatio(foreground, background) {
  const channel = (value) => {
    const normalized = value / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  const luminance = (hex) => {
    const rgb = hex.match(/[a-f\d]{2}/gi).map((part) => parseInt(part, 16));
    return (0.2126 * channel(rgb[0])) + (0.7152 * channel(rgb[1])) + (0.0722 * channel(rgb[2]));
  };
  const light = Math.max(luminance(foreground), luminance(background));
  const dark = Math.min(luminance(foreground), luminance(background));
  return (light + 0.05) / (dark + 0.05);
}

describe('Admin menu status button styles', () => {
  it('keeps status actions readable in every interactive state', () => {
    const css = readStatic('../../static/css/menu_editor.css');
    const scope = '.menu-week__status .menu-editor-actions';

    expect(css).toContain(`${scope} .yp-btn-primary`);
    expect(css).toContain(`${scope} .yp-btn-primary:hover`);
    expect(css).toContain(`${scope} .yp-btn-secondary:hover`);
    expect(css).toContain(`${scope} .yp-btn:focus-visible`);
    expect(css).toContain(`${scope} .yp-btn:active`);
    expect(css).toContain(`${scope} .yp-btn:disabled`);
    expect(css).toContain('color: #fff;');
    expect(css).toContain('color: var(--yp-color-text, var(--text));');
  });

  it('uses a distinct but restrained warning treatment for unpublish', () => {
    const css = readStatic('../../static/css/menu_editor.css');

    expect(css).toContain('.menu-editor-unpublish-button');
    expect(css).toContain('var(--yp-color-warning');
  });

  it('keeps dark-theme status button text above the 4.5:1 contrast threshold', () => {
    const css = readStatic('../../static/css/menu_editor.css');

    expect(css).toContain('background: #5a351f;');
    expect(css).toContain('background: #704326;');
    expect(css).toContain('background: #102945;');
    expect(css).toContain('background: #173854;');
    expect(contrastRatio('#ffedd5', '#5a351f')).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio('#fff7ed', '#704326')).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio('#eaf7f8', '#102945')).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio('#ffffff', '#173854')).toBeGreaterThanOrEqual(4.5);
  });
});
