#!/usr/bin/env node
import sharp from 'sharp';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const root = resolve(__dirname, '../../');
const staticDir = resolve(root, 'static');
const srcSvg = resolve(staticDir, 'img', 'logo-compact.svg');

async function main(){
  const svg = await readFile(srcSvg);
  // PNG icons
  await sharp(svg).resize(192,192).png().toFile(resolve(staticDir, 'icon-192.png'));
  await sharp(svg).resize(512,512).png().toFile(resolve(staticDir, 'icon-512.png'));
  await sharp(svg).resize(180,180).png().toFile(resolve(staticDir, 'apple-touch-icon.png'));
  // favicon.ico multi-size 16/32/48
  // Minimal fallback: write a 48x48 favicon.ico (acceptable for most browsers)
  await sharp(svg).resize(48,48).toFile(resolve(staticDir, 'favicon.ico'));
  console.log('Icons written to /static');
}

main().catch(err=>{ console.error(err); process.exit(1); });
