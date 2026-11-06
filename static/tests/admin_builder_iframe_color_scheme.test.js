import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Kommun embedded Builder iframe color scheme', () => {
  it('scopes normal color scheme to the Kommun Builder iframe', () => {
    const appShellCss = readStatic('../../static/css/app_shell.css');
    const rule = appShellCss.match(
      /\.yp-modal-host\[data-admin-week-builder-host\]\[data-modal-host-mode="child-owned-card"\] \.yp-modal-host__frame \{[\s\S]*?\n\}/,
    )?.[0] || '';

    expect(rule).toContain('color-scheme: normal;');
    expect(rule).not.toContain('background:');
    expect(appShellCss).not.toContain(
      '.yp-modal-host[data-modal-host-mode="child-owned-card"] .yp-modal-host__frame {\n  color-scheme: normal;',
    );
  });

  it('preserves the generic child-owned transport contract', () => {
    const appShellCss = readStatic('../../static/css/app_shell.css');
    const panelRule = appShellCss.match(
      /\.yp-modal-host\[data-modal-host-mode="child-owned-card"\] \.yp-modal-host__panel \{[\s\S]*?\n\}/,
    )?.[0] || '';
    const frameRule = appShellCss.match(
      /\.yp-modal-host\[data-modal-host-mode="child-owned-card"\] \.yp-modal-host__frame \{[\s\S]*?\n\}/,
    )?.[0] || '';

    expect(panelRule).toContain('background: transparent;');
    expect(panelRule).toContain('border: 0;');
    expect(panelRule).toContain('border-radius: 0;');
    expect(panelRule).toContain('box-shadow: none;');
    expect(frameRule).toContain('background: transparent;');
  });

  it('preserves the Builder card appearance', () => {
    const builderCss = readStatic('../../static/css/builder.css');
    const cardBaseRule = builderCss.match(
      /\.builder-workspace-v1 \.modal-content \{[\s\S]*?\n\}/,
    )?.[0] || '';
    const dishCardRule = builderCss.match(
      /\.builder-workspace-v1 \.modal-content-dish \{[\s\S]*?\n\}/,
    )?.[0] || '';

    expect(cardBaseRule).toContain(
      'background: linear-gradient(180deg, #fcfdfe 0%, #f2f6f9 100%);',
    );
    expect(cardBaseRule).toContain('border-radius: 24px;');
    expect(cardBaseRule).toContain('box-shadow: 0 28px 60px rgba(22, 37, 52, 0.24);');
    expect(dishCardRule).toContain('padding: 12px;');
  });
});
