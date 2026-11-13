import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('embedded Builder modal ownership', () => {
  it('uses fullscreen transport only for the admin week Builder host', () => {
    const appShellCss = readStatic('../../static/css/app_shell.css');
    const fullscreenHost = appShellCss.match(
      /\.yp-modal-host\[data-admin-week-builder-host\]\[data-modal-host-mode="child-owned-card"\] \{[\s\S]*?\n\}/,
    )?.[0] || '';
    const fullscreenPanel = appShellCss.match(
      /\.yp-modal-host\[data-admin-week-builder-host\]\[data-modal-host-mode="child-owned-card"\] \.yp-modal-host__panel \{[\s\S]*?\n\}/,
    )?.[0] || '';
    const fullscreenFrame = appShellCss.match(
      /\.yp-modal-host\[data-admin-week-builder-host\]\[data-modal-host-mode="child-owned-card"\] \.yp-modal-host__frame \{[\s\S]*?\n\}/,
    )?.[0] || '';

    expect(fullscreenHost).toContain('display: block;');
    expect(fullscreenHost).toContain('padding: 0;');
    expect(fullscreenPanel).toContain('position: absolute;');
    expect(fullscreenPanel).toContain('inset: 0;');
    expect(fullscreenPanel).toContain('width: 100vw;');
    expect(fullscreenPanel).toContain('height: 100vh;');
    expect(fullscreenFrame).toContain('position: absolute;');
    expect(fullscreenFrame).toContain('width: 100vw;');
    expect(fullscreenFrame).toContain('height: 100vh;');
    expect(appShellCss).not.toContain(
      '.yp-modal-host[data-admin-week-builder-host][data-modal-host-mode="shell-owned-card"]',
    );
  });

  it('keeps the parent and iframe as transparent, appearance-free transport layers', () => {
    const appShellCss = readStatic('../../static/css/app_shell.css');
    const childOwnedPanel = appShellCss.match(
      /\.yp-modal-host\[data-modal-host-mode="child-owned-card"\] \.yp-modal-host__panel \{[\s\S]*?\n\}/,
    )?.[0] || '';
    const childOwnedFrame = appShellCss.match(
      /\.yp-modal-host\[data-modal-host-mode="child-owned-card"\] \.yp-modal-host__frame \{[\s\S]*?\n\}/,
    )?.[0] || '';

    expect(childOwnedPanel).toContain('background: transparent;');
    expect(childOwnedPanel).toContain('border: 0;');
    expect(childOwnedPanel).toContain('box-shadow: none;');
    expect(childOwnedFrame).toContain('background: transparent;');
    expect(childOwnedFrame).not.toContain('box-shadow');
    expect(childOwnedFrame).not.toContain('clip-path');
  });

  it('keeps the child modal responsible for its natural card geometry', () => {
    const hostCss = readStatic('../../static/css/builder_editor_host.css');
    const modalRule = hostCss.match(
      /body\.builder-workspace-v1\.builder-editor-host \.modal \{[\s\S]*?\n\}/,
    )?.[0] || '';

    expect(modalRule).toContain('background: transparent;');
    expect(modalRule).not.toContain('padding: 0;');
    expect(modalRule).not.toContain('height: 100%;');
    expect(modalRule).not.toContain('width: 100%;');
  });
});
