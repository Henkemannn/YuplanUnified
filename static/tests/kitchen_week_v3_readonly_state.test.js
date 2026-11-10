import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const template = fs.readFileSync(
  path.resolve('templates/ui/kitchen_week_v3.html'),
  'utf8',
);

describe('Kitchen Weekview always-on completion template state', () => {
  it('does not gate the completion grid on the feature flag', () => {
    expect(template).not.toContain('vm.weekview_enabled');
    expect(template).toContain('{% set interactive = true %}');
    expect(template).not.toContain(
      'Färdigmarkering är inte aktiverad för denna arbetsplats.',
    );
  });
});
